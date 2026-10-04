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
        scenarios.regime(SimConfig(), "B3")


def test_calibrated_a3_present_population_hits_target_on_a_fresh_seed():
    """The arrival blend is calibrated on dev seed 101; a different seed lands near the target."""
    cfg = scenarios.regime(SimConfig(n_hosts=1_000, horizon_days=90, name="t"), "A3")
    assert cfg.placement.arrival_blend is not None
    s = engine.run(engine.prepare(worlds.generate(cfg, 7), cfg), R.Never(), budget_frac=0.0)
    assert abs(s["rho_tier_risk_horizon"] - cfg.placement.rho) < 0.04


def test_b1_cells_follow_the_week8_measurement():
    base = SimConfig(n_hosts=100, horizon_days=30)
    assert scenarios.regime(base, "B1-low").placement.regime == "random"  # negative: random
    hi = scenarios.regime(base, "B1-high").placement
    assert hi.regime == "rho" and 0 < hi.rho < 0.06


# --------------------------------------------------------------------------- regime E (Week 17)
def test_regime_e_sets_the_spread_of_log_kappa_and_keeps_its_order():
    from vmsim.entities import split

    base = SimConfig(n_hosts=200, horizon_days=30, name="t")
    med, sd = engine.kappa_reference(base.cost)
    assert 0.9 < sd < 1.2  # natural spread under v1's costs (tier 0.51, VM size the rest)
    res = set(split()["resident_rows"].tolist())
    for cell, target in scenarios.E_SIGMA.items():
        cfg = scenarios.regime(base, cell)
        assert cfg.placement.regime == "random" and cfg.cost.kappa_sigma == target
        v = engine.prepare(worlds.generate(cfg, 101), cfg).vm
        v0 = engine.prepare(worlds.generate(base, 101), base).vm
        keep = np.array([r in res for r in v["row"]])
        lk = np.log(v["fail_cost"][keep] / v["mem"][keep])
        lk0 = np.log(v0["fail_cost"][keep] / v0["mem"][keep])
        assert abs(lk.std() - target) < 0.1 * target + 0.03
        assert abs(np.median(lk) - med) < 0.15
        assert (np.argsort(lk0, kind="stable") == np.argsort(lk, kind="stable")).mean() > 0.99
        assert np.array_equal(v["mig_cost_est"], v0["mig_cost_est"])  # migration cost untouched


# --------------------------------------------------------------------------- regime B2 (Week 17)
def test_b2_tables_keep_the_margins_and_the_trace_association():
    from vmsim.copula import resident_tier_shares

    shares, cgt = scenarios.b2_tables()
    cgt = np.asarray(cgt)
    assert np.allclose(cgt.sum(1), 1) and abs(sum(shares) - 1) < 1e-6
    joint = cgt * np.asarray(resident_tier_shares())[:, None]  # tier x class
    assert np.allclose(joint.sum(0), shares, atol=1e-6)  # class margin = machine shares
    # the fitted table keeps the trace's odds ratios (IPF)
    import json

    cl = json.loads(scenarios.B2_CLASSES.read_text())["classes"]
    mix = np.array([c["tier_mix_low_med_high"] for c in cl])
    seed = np.asarray(shares)[:, None] * mix
    for a, b in ((0, 1), (2, 4)):
        orig = (seed[a, 0] * seed[b, 2]) / (seed[a, 2] * seed[b, 0])
        fit = (joint[0, a] * joint[2, b]) / (joint[2, a] * joint[0, b])
        assert abs(np.log(orig / fit)) < 1e-6


def test_b2_world_has_classes_by_risk_and_runs_clean():
    cfg = scenarios.regime(SimConfig(n_hosts=600, horizon_days=60, name="t"), "B2")
    w = worlds.generate(cfg, 7)
    shares = np.asarray(cfg.placement.class_shares)
    assert np.allclose(np.bincount(w.host_class, minlength=len(shares)) / 600, shares, atol=0.01)
    # classes are ordered by risk: class means of the day-0 risk are non-decreasing
    means = [w.host_risk0[w.host_class == k].mean() for k in range(len(shares))]
    assert np.all(np.diff(means) >= 0)
    prep = engine.prepare(w, cfg)
    s0 = engine.run(prep, R.Never(), budget_frac=0.0, check=True)
    s1 = engine.run(prep, R.Never(), budget_frac=0.0)
    assert s0["outcomes_sha256"] == s1["outcomes_sha256"]


def test_threshold_fills_a_small_budget_exactly():
    """Regression (4 Oct 2026): the host pre-filter used to cut the candidate list at 3 x the
    budget, so P2 used only about 88% of a 0.5% budget and tau had no effect there."""
    cfg = scenarios.regime(SimConfig(n_hosts=600, horizon_days=60, name="t"), "A1")
    prep = engine.prepare(worlds.generate(cfg, 101), cfg)
    s = engine.run(prep, R.Threshold(1e-6, "random", "P2"), budget_frac=0.005)
    assert s["budget_utilisation"] > 0.99
