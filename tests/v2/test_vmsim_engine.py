"""Week 13: engine, migration and accounting (SIM_SPEC sections 4-6, 12 and 14; gate G2)."""

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sim_helpers import MoveOnDay, constant_world, schedule_of

from vmsim import engine, migration, worlds
from vmsim.config import MigrationConfig, PlacementConfig, SimConfig
from vmsim.policies import reference as R


# ---------------------------------------------------------------- migration model
def test_precopy_zero_dirty_is_one_pass_plus_minimum_blackout():
    mc = MigrationConfig()
    d, b, sent = migration.precopy(np.array([4.0]), np.array([0.0]), 500.0, mc)
    assert b[0] == mc.blackout_converged_s
    assert np.isclose(d[0], 4 * 1024 / 500 + 1.0)
    assert np.isclose(sent[0], 4 * 1024)


def test_precopy_rounds_shrink_and_non_convergence_falls_back():
    mc = MigrationConfig()
    d, b, sent = migration.precopy(np.array([8.0, 8.0]), np.array([100.0, 480.0]), 500.0, mc)
    assert sent[0] > 8 * 1024 and d[0] > 8 * 1024 / 500  # re-sent pages
    assert b[1] == mc.blackout_fallback_s and d[1] == mc.blackout_fallback_s  # 480 >= 0.9 x 500


def test_lanes_share_bandwidth_and_queue():
    mc = MigrationConfig(max_concurrent=2)
    src = np.array([0, 0, 0, 1])
    ts, te, dur, _, _ = migration.schedule(src, np.full(4, 8.0), np.zeros(4), 5.0, mc)
    assert ts[0] == ts[1] == 5.0 and np.isclose(ts[2], te[0])  # third waits for lane 0
    assert ts[3] == 5.0 and dur[3] < dur[0]  # host 1 has one migration: the whole link


# ---------------------------------------------------------------- analytic checks (G2 #1)
def test_analytic_never_migrate_cost():
    """P0 with one static VM per host: cost = c x (hosts failing within T), exactly, and its
    mean matches N x p_T x c."""
    n, h, T = 20_000, 0.01, 30
    prep = constant_world(n, h, T)
    s = engine.run(prep, R.Never())
    first = prep.world.fail_t
    assert s["cost_total"] == pytest.approx(10.0 * (first < T).sum())
    p = 1 - (1 - h) ** T
    z = (s["interrupted_vms"] - n * p) / np.sqrt(n * p * (1 - p))
    assert abs(z) < 4


def test_analytic_migration_under_constant_hazard_is_pure_cost():
    """Moving every VM once at day 0 under a constant hazard: interruption probability is still
    1 - exp(-rT) (memoryless, cancellations included), so E[cost] = N (m + p_T c)."""
    n, h, T = 20_000, 0.01, 30
    prep = constant_world(n, h, T)
    s = engine.run(prep, MoveOnDay(0), check=True)
    assert s["migrations"] == n
    p = 1 - (1 - h) ** T
    z = (s["interrupted_vms"] - n * p) / np.sqrt(n * p * (1 - p))
    assert abs(z) < 4
    assert s["cost_migration"] > 0


def test_analytic_oracle_saves_almost_everything():
    n, h, T = 5_000, 0.01, 30
    prep = constant_world(n, h, T)
    p0 = engine.run(prep, R.Never())
    p7 = engine.run(prep, R.Oracle(), check=True)
    # left: failures inside a migration (seconds), and both destination candidates failing
    # before the next decision (about h^2 per move)
    assert p7["interrupted_vms"] <= 0.01 * p0["interrupted_vms"] + 2
    assert p7["cost_total"] < 0.1 * p0["cost_total"]


# ---------------------------------------------------------------- tie order (SIM_SPEC 2)
def _move_then_fail(which: str, dt: float):
    base = constant_world(2, 1e-9, 5, sched=schedule_of([]))
    mc = base.cfg.migration
    _, te, _, _, _ = migration.schedule(
        np.array([0]), base.vm["mem"][:1], base.vm["dirty"][:1], 0.0, mc
    )
    host = 0 if which == "source" else 1
    sched = schedule_of([(host, float(te[0]) + dt, 3.0)])
    prep = constant_world(2, 1e-9, 5, sched=sched)
    return engine.run(prep, MoveOnDay(0, hosts=[0]), check=True)


def test_source_failure_at_migration_end_interrupts():
    s = _move_then_fail("source", 0.0)
    assert s["interrupted_vms"] == 1 and s["interrupted_in_flight"] == 1


def test_source_failure_just_after_migration_end_is_safe():
    s = _move_then_fail("source", 1e-9)
    assert s["interrupted_vms"] == 0 and s["migrations_done"] >= 1


def test_destination_failure_at_migration_end_cancels_without_interruption():
    s = _move_then_fail("destination", 0.0)
    # host 1's own VM is interrupted; the migrating VM stays on host 0
    assert s["interrupted_vms"] == 1


# ---------------------------------------------------------------- invariants (SIM_SPEC 12)
@pytest.fixture(scope="module")
def small_prep():
    cfg = SimConfig(n_hosts=150, horizon_days=40, warmup_days=10)
    return engine.prepare(worlds.generate(cfg, 7), cfg)


POLICIES = [R.Never, R.Threshold, R.V1Rule, R.Oracle, R.RandomPick]


@settings(
    max_examples=12,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(
    seed=st.integers(1, 10_000),
    pol=st.sampled_from(POLICIES),
    budget=st.sampled_from([0.0, 0.005, 0.02, 0.2]),
    regime=st.sampled_from(["random", "adversarial"]),
    mult=st.sampled_from([0.0, 3.0]),
)
def test_invariants_hold(seed, pol, budget, regime, mult):
    from vmsim.config import FailureConfig

    cfg = SimConfig(
        n_hosts=60,
        horizon_days=30,
        warmup_days=5,
        budget_frac=budget,
        placement=PlacementConfig(regime=regime),
        failure=FailureConfig(non_disk_multiplier=mult),
    )
    prep = engine.prepare(worlds.generate(cfg, seed), cfg)
    s = engine.run(prep, pol(), check=True)  # raises InvariantError on any violation
    assert s["max_daily_overspend_gb"] <= 1e-9
    assert s["budget_utilisation"] <= 1 + 1e-9


def test_determinism_byte_identical(small_prep):
    a = engine.run(small_prep, R.Threshold())
    b = engine.run(small_prep, R.Threshold())
    cfg = small_prep.cfg
    again = engine.prepare(worlds.generate(cfg, 7), cfg)
    c = engine.run(again, R.Threshold())
    assert a["outcomes_sha256"] == b["outcomes_sha256"] == c["outcomes_sha256"]


def test_crn_failures_and_arrivals_identical_across_policies(small_prep):
    a = engine.prepare(small_prep.world, small_prep.cfg)
    assert np.array_equal(a.sched, small_prep.sched)
    assert np.array_equal(a.vm["t_arr"], small_prep.vm["t_arr"])
    assert np.array_equal(a.vm["row"], small_prep.vm["row"])
    s0 = engine.run(small_prep, R.Never())
    s1 = engine.run(small_prep, R.RandomPick())
    assert s0["host_failures"] == s1["host_failures"]
    assert s0["cost_interrupt_transient"] == s1["cost_interrupt_transient"]


def test_zero_budget_equals_never(small_prep):
    ref = engine.run(small_prep, R.Never(), budget_frac=0.0)["outcomes_sha256"]
    for pol in POLICIES[1:]:
        assert engine.run(small_prep, pol(), budget_frac=0.0)["outcomes_sha256"] == ref


def test_oracle_bounds_on_seeds():
    """P7 is never worse than the other reference policies, and not worse with more budget
    (SIM_SPEC invariant 9; checked on seeds, not proved: see policies/reference.Oracle)."""
    cfg = SimConfig(n_hosts=300, horizon_days=60, warmup_days=10)
    for seed in (1, 2, 3):
        prep = engine.prepare(worlds.generate(cfg, seed), cfg)
        p7 = engine.run(prep, R.Oracle())["cost_total"]
        for pol in (R.Never, R.Threshold, R.V1Rule, R.RandomPick):
            assert p7 <= engine.run(prep, pol())["cost_total"] + 1e-9
        costs = [engine.run(prep, R.Oracle(), budget_frac=b)["cost_total"] for b in (0.005, 0.02)]
        assert costs[1] <= costs[0] * 1.02


def test_outputs_written(tmp_path, small_prep):
    s = engine.run(small_prep, R.V1Rule(), out_dir=tmp_path)
    import json

    import pandas as pd

    meta = json.loads((tmp_path / "summary.json").read_text())
    assert meta["config_hash"] == s["config_hash"] and meta["git_sha"]
    out = pd.read_parquet(tmp_path / "outcomes.parquet")
    assert set(out["kind"]) <= {"interrupt", "transient", "migration"}
    assert len(pd.read_parquet(tmp_path / "daily.parquet")) == 50


# ---------------------------------------------------------------- self-calibration with repairs
def test_self_calibration_across_repairs():
    """Failures in (d, d + 30] of hosts up at d match the renewal oracle's sum of p_H."""
    cfg = SimConfig(n_hosts=1_000, horizon_days=330, warmup_days=30)
    prep = engine.prepare(worlds.generate(cfg, 11), cfg)
    pred = engine.make_predictor(prep)
    obs = exp = var = 0.0
    for d in (60, 150, 240):
        life_start = np.full(cfg.n_hosts, -1)
        up = np.ones(cfg.n_hosts, dtype=bool)
        for r in prep.sched:
            if r["t_fail"] < d:
                life_start[r["host"]] = int(np.ceil(r["t_repair"]))
                up[r["host"]] = np.ceil(r["t_repair"]) <= d
        p = pred.score(d, life_start).p_h
        nxt = np.array(
            [
                f[np.searchsorted(f, d)] if np.searchsorted(f, d) < len(f) else np.inf
                for f in prep.host_fails
            ]
        )
        obs += ((nxt < d + 30) & up).sum()
        exp += p[up].sum()
        var += (p[up] * (1 - p[up])).sum()
    assert abs(obs - exp) < 4 * np.sqrt(var), (obs, exp)


# ---------------------------------------------------------------- v1 regression (G2 #3)
def test_v1_regression_within_one_percent():
    from vmsim import v1_regression

    r = v1_regression.run()
    assert r["pass"], r
    assert r["cost_sensitive"]["migrations"] == 5_116
    assert r["threshold_matched"]["migrations"] == 5_522
