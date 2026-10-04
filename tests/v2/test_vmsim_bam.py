"""Week 15: BAM (P4) and its variants."""

import numpy as np
import pytest

from vmsim import engine, scenarios, worlds
from vmsim.config import SimConfig
from vmsim.policies import reference as R
from vmsim.policies.bam import BAM, uniform_constants
from vmsim.policies.base import Observation


@pytest.fixture(scope="module")
def preps():
    out = []
    for cell, seed in (("A1", 101), ("A3", 102), ("C", 103)):
        cfg = scenarios.regime(SimConfig(n_hosts=200, horizon_days=60, warmup_days=10), cell)
        out.append(engine.prepare(worlds.generate(cfg, seed), cfg))
    return out


@pytest.mark.parametrize("order", ["random", "smallest", "largest"])
def test_p_only_bam_equals_threshold_decision_for_decision(preps, order):
    """Plan Week 15, task 5: uniform c and m, no urgency, --p-only => P2 with tau = m / c."""
    c0, m0 = 10.0, 0.05  # tau = 0.005: most hosts qualify, so the budget binds
    for prep in preps:
        bam = BAM(urgency=False, c_uniform=c0, m_uniform=m0, p_only=True, order=order)
        p2 = R.Threshold(m0 / c0 * (1 + 1e-12), order, "P2")
        a = engine.run(prep, bam, budget_frac=0.01)
        b = engine.run(prep, p2, budget_frac=0.01)
        assert a["migrations"] == b["migrations"] > 0
        assert a["outcomes_sha256"] == b["outcomes_sha256"]


def test_uniform_constants_are_positive():
    c, m = uniform_constants()
    assert c > 0 and m > 0 and m / c < 1


def _obs(p_host, mem, host, fail_cost, mig_cost, mig_s, day=0):
    n = len(mem)
    return Observation(
        day=day,
        h_days=30,
        p_h=np.asarray(p_host, float),
        e_ttf=np.full(len(p_host), 100.0),
        host_up=np.ones(len(p_host), bool),
        host_free_gb=np.full(len(p_host), 100.0),
        vm=np.arange(n),
        vm_host=np.asarray(host),
        vm_mem_gb=np.asarray(mem, float),
        vm_tier=np.full(n, 2),
        vm_age_days=np.full(n, 5.0),
        vm_fail_cost=np.asarray(fail_cost, float),
        vm_survival=np.ones(n),
        vm_mig_cost=np.asarray(mig_cost, float),
        vm_mig_s=np.asarray(mig_s, float),
        rng=np.random.default_rng(0),
    )


def test_density_ranking_and_positive_benefit_only():
    # host 0 risky, host 1 safe; VM 2 has negative benefit and must not appear
    obs = _obs([0.5, 0.01], [4, 8, 4], [0, 0, 1], [10, 10, 10], [0.1, 0.1, 0.2], [5, 5, 5])
    out = BAM(urgency=False).decide(obs, 100)
    assert list(out) == [0, 1]  # same benefit, smaller GB first (higher density)


def _reference_greedy(obs, lanes):
    """Brute force: at each step recompute every remaining VM's benefit with its host's
    current queue, take the highest density with b > 0."""
    p = obs.p_h[obs.vm_host]
    lam = -np.log1p(-p) / obs.h_days
    ahead = np.zeros(len(obs.p_h))
    left, out = list(range(len(obs.vm))), []
    while left:
        t = ahead[obs.vm_host[left]] + obs.vm_mig_s[left] / 86_400
        b = p[left] * obs.vm_fail_cost[left] * np.exp(-lam[left] * t) - obs.vm_mig_cost[left]
        dens = b / obs.vm_mem_gb[left]
        k = int(np.argmax(dens))
        if b[k] <= 0:
            break
        i = left.pop(k)
        out.append(i)
        ahead[obs.vm_host[i]] += obs.vm_mig_s[i] / 86_400 / lanes
    return out


def test_queue_recompute_matches_brute_force():
    """With long migrations on risky hosts, e falls with queue position; the lazy heap gives the
    same sequence as recomputing everything after each pick."""
    rng = np.random.default_rng(3)
    for _ in range(20):
        n_hosts, n = 4, 12
        obs = _obs(
            rng.uniform(0.3, 0.99, n_hosts),
            rng.uniform(1, 16, n),
            rng.integers(0, n_hosts, n),
            rng.choice([3.0, 6.0, 10.0], n),
            rng.uniform(0.01, 2.0, n),
            rng.uniform(0.5, 6.0, n) * 86_400,
        )
        for lanes in (1, 2):
            assert list(BAM(lanes=lanes).decide(obs, 1e6)) == _reference_greedy(obs, lanes)


@pytest.mark.parametrize("w", ["gb", "time", "cost"])
def test_variants_respect_invariants(preps, w):
    s = engine.run(preps[1], BAM(w), budget_frac=0.02, check=True)
    assert s["budget_utilisation"] <= 1 + 1e-9


def test_zero_budget_is_never(preps):
    ref = engine.run(preps[0], R.Never(), budget_frac=0.0)["outcomes_sha256"]
    assert engine.run(preps[0], BAM(), budget_frac=0.0)["outcomes_sha256"] == ref
