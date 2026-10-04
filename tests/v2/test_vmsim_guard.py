"""Week 16: P6 guard, regime D and the drifting / pure-noise predictors."""

import numpy as np
import pytest

from vmsim import engine, scenarios, worlds
from vmsim.config import SimConfig
from vmsim.policies.bam import BAM
from vmsim.policies.guard import SafeGuard, _kept, reliability_slope
from vmsim.policies.reference import Threshold


def test_reliability_slope_is_one_when_calibrated_and_low_for_noise():
    rng = np.random.default_rng(0)
    p = rng.beta(0.5, 20, 200_000)
    y = rng.uniform(size=len(p)) < p
    assert abs(reliability_slope(p, y) - 1) < 0.1
    assert abs(reliability_slope(rng.permutation(p), y)) < 0.15


def test_kept_is_the_engines_first_fit_rule():
    gb = np.array([5.0, 8.0, 2.0, 1.0])
    assert list(_kept(np.array([0, 1, 2, 3]), gb, 9.0)) == [0, 2, 3]  # 8 GB skipped, rest fit


def test_alpha_spending_sums_to_alpha():
    a = 0.05
    assert abs(sum(a * 6 / (np.pi**2 * k**2) for k in range(1, 200_000)) - a) < 1e-5


@pytest.fixture(scope="module")
def d_prep():
    cfg = scenarios.regime(SimConfig(n_hosts=400, horizon_days=200, name="t"), "D")
    return engine.prepare(worlds.generate(cfg, 106), cfg)


def test_regime_d_path_rho_rises_after_mid_run(d_prep):
    """The generator's intended path: the correlation of the VMs present rises after the
    switch day (rho_L 0.1 -> 0.6)."""
    import tempfile
    from pathlib import Path

    import pandas as pd

    from vmsim.policies.reference import Never

    pc = d_prep.cfg.placement
    assert pc.switch_day == d_prep.cfg.warmup_days + d_prep.cfg.horizon_days // 2
    with tempfile.TemporaryDirectory() as d:
        engine.run(d_prep, Never(), budget_frac=0.0, out_dir=Path(d))
        daily = pd.read_parquet(Path(d) / "daily.parquet").dropna(subset=["rho_tier_risk"])
    before = daily[(daily.day >= 30) & (daily.day < pc.switch_day)]["rho_tier_risk"].mean()
    after = daily[daily.day >= pc.switch_day + 30]["rho_tier_risk"].mean()
    assert before < 0.2 < 0.4 < after


def test_drifting_predictor_follows_its_gamma_path(d_prep):
    pred = engine.make_predictor(d_prep, "drift", gamma=0.7)
    mid = d_prep.cfg.placement.switch_day
    end = d_prep.cfg.warmup_days + d_prep.cfg.horizon_days
    assert pred.gamma(0) == 1.0 and pred.gamma(mid) == 1.0
    assert abs(pred.gamma(end) - 0.7) < 1e-12
    assert 0.7 < pred.gamma((mid + end) // 2) < 1.0


def test_pure_noise_keeps_the_marginal_and_loses_the_ranking(d_prep):
    o = engine.make_predictor(d_prep)
    n = engine.make_predictor(d_prep, "noise")
    a, b = o.score(50).p_h, n.score(50).p_h
    assert np.allclose(np.sort(a), np.sort(b))
    assert abs(np.corrcoef(a, b)[0, 1]) < 0.2


def test_guard_never_switches_on_pure_noise(d_prep):
    g = SafeGuard(Threshold(0.1, "smallest", "P2"))
    engine.run(d_prep, g, predictor=engine.make_predictor(d_prep, "noise"), budget_frac=0.02)
    assert g.switches == [] and g.mode_days["BAM"] == 0
    assert g.looks > 0


def test_guard_logs_evidence_and_is_deterministic(d_prep):
    runs = []
    for _ in range(2):
        g = SafeGuard(Threshold(0.1, "smallest", "P2"), BAM())
        s = engine.run(d_prep, g, budget_frac=0.02, check=True)
        runs.append((s["outcomes_sha256"], [(x["day"], x["to"]) for x in g.switches]))
        for rec in g.look_log:
            assert {"delta_hat", "lower", "slope", "events", "alpha_k", "mode"} <= set(rec)
    assert runs[0] == runs[1]


def test_guard_in_p2_mode_equals_p2(d_prep):
    """If the audit can never pass, P6 is P2 decision for decision."""
    g = SafeGuard(Threshold(0.1, "smallest", "P2"), min_events=10**9)
    a = engine.run(d_prep, g, budget_frac=0.02)
    b = engine.run(d_prep, Threshold(0.1, "smallest", "P2"), budget_frac=0.02)
    assert a["outcomes_sha256"] == b["outcomes_sha256"]
