"""Week 15: P5, Narya-inspired."""

import numpy as np
import pytest

from vmsim import engine, scenarios, worlds
from vmsim.config import SimConfig
from vmsim.policies import reference as R
from vmsim.policies.narya import ACTIONS, Narya


@pytest.fixture(scope="module")
def prep():
    cfg = scenarios.regime(SimConfig(n_hosts=300, horizon_days=120, warmup_days=10), "A3")
    return engine.prepare(worlds.generate(cfg, 104), cfg)


@pytest.mark.parametrize("variant", ["simple", "faithful"])
def test_runs_with_invariants_and_learns(prep, variant):
    pol = Narya(variant)
    s = engine.run(prep, pol, budget_frac=0.02, check=True)
    assert pol.updates > 0  # episodes ended and posteriors were updated
    acts = {a for b in pol.action_counts().values() for a in b}
    assert acts <= set(ACTIONS[variant]) and len(acts) >= 2  # explores more than one action
    assert s["budget_utilisation"] <= 1 + 1e-9


@pytest.mark.parametrize("variant", ["simple", "faithful"])
def test_deterministic(prep, variant):
    a = engine.run(prep, Narya(variant), budget_frac=0.02)
    b = engine.run(prep, Narya(variant), budget_frac=0.02)
    assert a["outcomes_sha256"] == b["outcomes_sha256"]


def test_reused_instance_is_reset_between_runs(prep):
    pol = Narya("faithful")
    a = engine.run(prep, pol, budget_frac=0.02)
    b = engine.run(prep, pol, budget_frac=0.02)
    assert a["outcomes_sha256"] == b["outcomes_sha256"]


def test_zero_budget_means_no_action_at_all(prep):
    ref = engine.run(prep, R.Never(), budget_frac=0.0)["outcomes_sha256"]
    assert engine.run(prep, Narya("faithful"), budget_frac=0.0)["outcomes_sha256"] == ref


def test_sticky_one_episode_per_host_at_a_time(prep):
    pol = Narya("simple")
    engine.run(prep, pol, budget_frac=0.02)
    starts: dict[int, list[int]] = {}
    for day, h, _, _ in pol.log:
        starts.setdefault(h, []).append(day)
    # a host is re-decided only after its window (H days) or a new life
    gaps = [np.diff(v).min() for v in starts.values() if len(v) > 1]
    assert all(g >= 1 for g in gaps)
    assert len(pol.log) == sum(len(v) for v in starts.values())


def test_avoid_marks_reduce_arrivals_on_flagged_hosts(prep):
    """Avoid-allocation must change where arrivals go (otherwise the action does nothing)."""
    only_avoid = Narya("faithful", explore=0.0)
    only_avoid._choose = lambda bucket, rng: "ua"  # force the action
    a = engine.run(prep, only_avoid, budget_frac=0.02)
    b = engine.run(prep, R.Never(), budget_frac=0.02)
    assert a["migrations"] == 0 and a["outcomes_sha256"] != b["outcomes_sha256"]
