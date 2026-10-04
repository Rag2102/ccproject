import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from vmsim import placement
from vmsim.entities import sample_vms


@pytest.fixture(scope="module")
def world():
    rng = np.random.default_rng(1)
    n_hosts = 1_500
    vms = sample_vms(16 * n_hosts, rng)  # 16 VMs per host, as in v1
    cap = np.full(n_hosts, 144.0)  # the config default: about 70% full
    risk = rng.lognormal(-6, 1.0, n_hosts)  # continuous host risk
    return vms, cap, risk


def used(host, vms, n):
    return np.bincount(host, weights=vms.mem_gb, minlength=n)


@pytest.mark.parametrize("target", [0.0, 0.15, 0.30, 0.45])
def test_rho_within_002_of_target(world, target):
    vms, cap, risk = world
    host, _, r = placement.rho_controlled(vms, cap, risk, target, np.random.default_rng(2))
    assert abs(placement.achieved_rho(vms.tier, risk, host) - target) <= 0.02
    assert abs(r - target) <= 0.02
    assert (used(host, vms, len(cap)) <= cap + 1e-9).all()


def test_random_is_uncorrelated_and_fits(world):
    vms, cap, risk = world
    host = placement.random(vms, cap, np.random.default_rng(3))
    assert abs(placement.achieved_rho(vms.tier, risk, host)) < 0.03
    assert (used(host, vms, len(cap)) <= cap + 1e-9).all()


def test_adversarial_is_the_most_correlated(world):
    vms, cap, risk = world
    adv = placement.adversarial(vms, cap, risk, np.random.default_rng(4))
    r_adv = placement.achieved_rho(vms.tier, risk, adv)
    _, _, r_max = placement.rho_controlled(vms, cap, risk, 0.0, np.random.default_rng(4))
    assert (
        r_adv > 0.5
        and r_adv
        >= placement.achieved_rho(
            vms.tier, risk, placement.rho_blend(vms, cap, risk, 1.0, np.random.default_rng(4))
        )
        - 0.02
    )


def test_slots_capacity_is_v1(world):
    vms, cap, risk = world
    host = placement.rho_blend(vms, cap, risk, 0.5, np.random.default_rng(5), capacity="slots")
    counts = np.bincount(host, minlength=len(cap))
    assert counts.max() - counts.min() <= 1 and counts.sum() == len(vms)


def test_trace_draws_tiers_given_class(world):
    vms, cap, risk = world
    cls = (risk > np.median(risk)).astype(int)
    table = np.array([[0.6, 0.39, 0.01], [0.2, 0.6, 0.2]])
    host, tier = placement.trace(vms, cap, cls, table, np.random.default_rng(6))
    for c in (0, 1):
        share = np.bincount(tier[cls[host] == c], minlength=3) / (cls[host] == c).sum()
        assert np.allclose(share, table[c], atol=0.02)


def test_placement_never_changes_vms(world):
    vms, cap, risk = world
    before = (vms.mem_gb.copy(), vms.tier.copy())
    placement.adversarial(vms, cap, risk, np.random.default_rng(7))
    assert np.array_equal(before[0], vms.mem_gb) and np.array_equal(before[1], vms.tier)


@settings(max_examples=15, deadline=None)
@given(seed=st.integers(0, 2**32 - 1), blend=st.floats(0, 1))
def test_deterministic_and_within_capacity(world, seed, blend):
    vms, cap, risk = world
    a = placement.rho_blend(vms, cap, risk, blend, np.random.default_rng(seed))
    b = placement.rho_blend(vms, cap, risk, blend, np.random.default_rng(seed))
    assert a.tobytes() == b.tobytes()
    assert (used(a, vms, len(cap)) <= cap + 1e-9).all()
