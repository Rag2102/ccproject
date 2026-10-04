"""Week 14: reference policies, P2 tuning, budgets and regimes (PROTOCOL sections 2-3)."""

import numpy as np
import pytest

from vmsim import engine, placement, scenarios, worlds
from vmsim.config import SimConfig
from vmsim.copula import latent_to_spearman
from vmsim.policies import reference as R
from vmsim.policies.tune import tune_p2


def preps(seeds, **kw):
    cfg = SimConfig(n_hosts=120, horizon_days=60, warmup_days=10, **kw)
    return [engine.prepare(worlds.generate(cfg, s), cfg) for s in seeds]


@pytest.fixture(scope="module")
def ten():
    return preps(range(101, 111))


def test_threshold_above_every_score_is_never(ten):
    p = ten[0]
    assert (
        engine.run(p, R.Threshold(1.0, "random"))["outcomes_sha256"]
        == engine.run(p, R.Never())["outcomes_sha256"]
    )


@pytest.mark.parametrize("b", [0.005, 0.01, 0.02, 0.05])
def test_budget_levels_respected_and_counted(ten, b):
    s = engine.run(ten[0], R.RandomPick(), budget_frac=b, check=True)
    assert s["budget_utilisation"] <= 1 + 1e-9
    assert s["budget_utilisation"] > 0.9  # P8 spends it, to within one VM a day
    assert s["migrations"] > 0  # counts are reported next to GB


def test_tune_p2_uses_the_budget(ten):
    tp = tune_p2(ten[:3], 0.02, steps=6)
    assert tp["order"] in ("smallest", "largest", "random")
    win = next(r for r in tp["table"] if r["order"] == tp["order"])
    assert win["reached"] and win["util"] >= 0.95


def test_cost_tuned_p2_is_never_worse_than_p0_on_dev_seeds(ten):
    tp = tune_p2(ten[:3], 0.02, criterion="cost")
    p0 = np.mean([engine.run(p, R.Never())["cost_total"] for p in ten[:3]])
    assert min(r["cost"] for r in tp["table"]) <= p0 + 1e-9


def test_random_is_not_better_than_tuned_threshold_on_ten_seeds(ten):
    """PROTOCOL section 2 sanity check, with P2 tuned on its cost (the budget-filling P2 can
    lose to P8: smallest-first moves more, smaller VMs at a higher cost per GB)."""
    tp = tune_p2(ten, 0.02, criterion="cost")
    p2 = [engine.run(p, R.Threshold(tp["tau"], tp["order"], "P2"), budget_frac=0.02) for p in ten]
    p8 = [engine.run(p, R.RandomPick(), budget_frac=0.02) for p in ten]
    assert np.mean([r["cost_total"] for r in p8]) >= np.mean([r["cost_total"] for r in p2])


def test_latent_axis_is_monotone_and_zero_at_zero():
    vals = [latent_to_spearman(r) for r in (0.0, 0.15, 0.3, 0.6, 0.9)]
    assert abs(vals[0]) < 1e-9 and np.all(np.diff(vals) > 0)


def test_a3_world_hits_its_spearman_target():
    cfg = scenarios.regime(SimConfig(n_hosts=400, horizon_days=30), "A3")
    w = worlds.generate(cfg, 5)
    got = placement.achieved_rho(w.vm_tier, w.host_risk0, w.vm_host)
    assert abs(got - cfg.placement.rho) < 0.02


def test_unknown_regimes_are_refused():
    with pytest.raises(ValueError):
        scenarios.regime(SimConfig(), "B1")
