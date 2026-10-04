"""
Tests for webapp/core.py -- the shared inference/decision logic both
deployments (Render's app.py and AWS's lambda_function.py) call into.
Nothing here should ever need a live server: everything importable and
callable in isolation, exactly the point of factoring it out of app.py.

Importing `core` loads the real trained models and reference data from
models/ and data/processed/ (see core.py's module-level load) -- these are
small, git-tracked files, so this runs the same way in CI as it does
locally, no fixtures or mocking required.
"""
import json

import numpy as np
import pytest

import core


# ---------------------------------------------------------------------------
# get_meta -- the shape both deployments render their controls from
# ---------------------------------------------------------------------------
def test_get_meta_shape():
    meta = core.get_meta()

    assert meta["model_groups"] == core.MODEL_GROUPS
    assert meta["model_groups"] == sorted(meta["model_groups"])
    assert len(meta["model_groups"]) > 0

    assert meta["size_tiers"] == core.SIZE_TIERS
    assert set(meta["criticality_tiers"]) == set(core.CRITICALITY_MAP.keys())

    assert isinstance(meta["tau_default"], float)
    assert 0.0 < meta["tau_default"] < 1.0

    assert len(meta["headline"]) > 0
    assert len(meta["comparison"]) > 0
    # every model comparison row needs a human-readable name -- this is
    # exactly the kind of internal-label leak ("(task 3)") that made it to
    # the live page once already; a name with digits-in-parens is the
    # specific shape that leak took, so it's what this guards against.
    for row in meta["comparison"]:
        assert "task" not in row["model"].lower()

    assert meta["bin_days"] == core.BIN_DAYS
    assert meta["lookahead_days"] == core.LOOKAHEAD_DAYS
    assert meta["max_age_days"] == core.MAX_AGE_DAYS


# ---------------------------------------------------------------------------
# survival_and_ttf -- pure math, tested against hand-constructed hazard
# curves rather than a real model's output, so the expected values are
# exact rather than "whatever the model happens to produce."
# ---------------------------------------------------------------------------
def test_survival_and_ttf_zero_hazard_never_fails():
    n = 50
    bins = np.arange(n) * core.BIN_DAYS
    hazard = np.zeros(n)
    expected_ttf, median_ttf, p_fail = core.survival_and_ttf(bins, hazard, start_idx=0)

    # survival never drops -- expected TTF is the full horizon (n bins of
    # width BIN_DAYS, since survival is tracked at n+1 points: t=0 plus one
    # per hazard bin), no median crossing exists, and the near-term failure
    # probability is exactly 0.
    horizon_days = n * core.BIN_DAYS
    assert expected_ttf == pytest.approx(horizon_days)
    assert median_ttf is None
    assert p_fail == 0.0


def test_survival_and_ttf_certain_immediate_failure():
    n = 50
    bins = np.arange(n) * core.BIN_DAYS
    hazard = np.zeros(n)
    hazard[0] = 1.0  # certain failure in the very first bin
    expected_ttf, median_ttf, p_fail = core.survival_and_ttf(bins, hazard, start_idx=0)

    # survival goes 1.0 -> 0.0 across exactly one bin (t=0 is always
    # survival=1.0 by construction; the hazard only applies across the
    # first bin), so both the trapezoidal-integral TTF and the linearly
    # interpolated median TTF land at the same halfway point: 0.5 * bin_days.
    assert expected_ttf == pytest.approx(0.5 * core.BIN_DAYS)
    assert median_ttf == pytest.approx(0.5 * core.BIN_DAYS)
    assert p_fail == 1.0


def test_survival_and_ttf_start_idx_shifts_the_window():
    # a hazard curve that's certain-failure at bin 3 but zero everywhere
    # else should behave like the zero-hazard case when starting after it,
    # and like the certain-failure case when starting at it.
    n = 20
    bins = np.arange(n) * core.BIN_DAYS
    hazard = np.zeros(n)
    hazard[3] = 1.0

    _, median_after, p_fail_after = core.survival_and_ttf(bins, hazard, start_idx=4)
    assert median_after is None
    assert p_fail_after == 0.0

    _, median_at, p_fail_at = core.survival_and_ttf(bins, hazard, start_idx=3)
    assert median_at == pytest.approx(0.5 * core.BIN_DAYS)
    assert p_fail_at == 1.0


# ---------------------------------------------------------------------------
# migration_and_failure_cost -- the Clark et al. pre-copy formula. Recomputed
# independently here (not just re-reading core.py's own formula back) so a
# future accidental change to the formula actually gets caught.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("size_tier", core.SIZE_TIERS)
@pytest.mark.parametrize("criticality_tier", list(core.CRITICALITY_MAP.keys()))
def test_migration_and_failure_cost_matches_formula(size_tier, criticality_tier):
    result = core.migration_and_failure_cost(size_tier, criticality_tier)

    prof = core.SIZE_TIER_PROFILE[size_tier]
    crit_w = core.CRITICALITY_MAP[criticality_tier]
    memory_mb = prof["memory_gb"] * 1024
    dirty_rate_mbps = (prof["avg_cpu"] / 100.0) * core.MAX_DIRTY_RATE_MBPS_AT_100PCT_CPU
    converges = dirty_rate_mbps < 0.9 * core.MIGRATION_BANDWIDTH_MBPS

    assert result["precopy_converges"] == converges
    if converges:
        expected_time_s = memory_mb / (core.MIGRATION_BANDWIDTH_MBPS - dirty_rate_mbps)
        # core.py rounds this field to 2dp before returning it (it's a
        # user-facing API value); compare against the same rounding rather
        # than the raw float, or this fails on every non-round input.
        assert result["migration_time_s"] == pytest.approx(round(expected_time_s, 2), abs=0.005)
        assert result["migration_blackout_s"] == pytest.approx(core.BASE_BLACKOUT_S)
    else:
        assert result["migration_time_s"] == pytest.approx(core.STOPCOPY_FALLBACK_S)
        assert result["migration_blackout_s"] == pytest.approx(core.STOPCOPY_FALLBACK_S)

    expected_failure_cost = core.UNMITIGATED_FAILURE_DOWNTIME_MIN * crit_w
    assert result["failure_customer_cost_min"] == pytest.approx(expected_failure_cost, rel=1e-6)

    assert result["total_migration_cost_min"] == pytest.approx(
        result["migration_customer_cost_min"] + result["migration_resource_cost_min"], rel=1e-6
    )


def test_migration_and_failure_cost_criticality_ordering():
    # a "high" criticality VM should always cost more to lose (and cost the
    # same or more to migrate around a customer-visible blackout) than a
    # "low" criticality one on the same hardware -- this is the whole point
    # of the criticality weighting, so it's worth locking in directly.
    size_tier = core.SIZE_TIERS[0]
    high = core.migration_and_failure_cost(size_tier, "high")
    low = core.migration_and_failure_cost(size_tier, "low")

    assert high["failure_customer_cost_min"] > low["failure_customer_cost_min"]
    assert high["migration_customer_cost_min"] >= low["migration_customer_cost_min"]


# ---------------------------------------------------------------------------
# run_predict -- the actual request/response contract both deployments
# expose. This is a regression test against a known-good value verified
# earlier by hand (byte-identical across the pre- and post-redesign
# webapp): if this ever changes, either the model, the data, or the
# request-handling logic moved, and it's worth knowing which.
# ---------------------------------------------------------------------------
GOLDEN_PAYLOAD = {
    "model_grp": "ST4000DM000",
    "age_days": 900,
    "criticality_tier": "high",
    "size_tier": "large",
    "which_model": "histgbm",
}


def test_run_predict_histgbm_golden_regression():
    result = core.run_predict(GOLDEN_PAYLOAD)

    assert result["model_used"] == "Calibrated HistGBM"
    assert result["p_fail_within_window"] == pytest.approx(0.0026867945771869017, rel=1e-9)
    assert result["expected_ttf_days"] == pytest.approx(6360.3, rel=1e-6)
    assert result["mc_dropout_std"] is None  # only the gqat path computes this


def test_run_predict_threshold_matches_tau_default():
    result = core.run_predict(GOLDEN_PAYLOAD)

    assert result["threshold"]["tau"] == pytest.approx(core.TAU_DEFAULT)
    expected_migrate = result["p_fail_within_window"] > core.TAU_DEFAULT
    assert result["threshold"]["migrate"] == expected_migrate


def test_run_predict_gqat_produces_uncertainty():
    payload = dict(GOLDEN_PAYLOAD, which_model="gqat")
    result = core.run_predict(payload)

    assert result["model_used"] == "GQAT-Net-inspired (NumPy, isotonic-calibrated)"
    assert result["mc_dropout_std"] is not None
    assert result["mc_dropout_std"] >= 0.0
    assert 0.0 <= result["p_fail_within_window"] <= 1.0


def test_run_predict_never_leaks_internal_task_labels():
    # the same regression this project already hit once for real (see
    # test_get_meta_shape) -- any future model_used string should stay
    # presenter-facing, not an internal task number.
    for which_model in ("histgbm", "gqat"):
        result = core.run_predict(dict(GOLDEN_PAYLOAD, which_model=which_model))
        assert "task" not in result["model_used"].lower()


# ---------------------------------------------------------------------------
# Input validation (task 40) -- run_predict() must reject a malformed or
# out-of-range request with a clean InputValidationError carrying
# field-level messages, never let a bad body reach deep model code as a
# raw KeyError/TypeError/ValueError (which would surface as an unhandled
# 500 through both webapp/app.py and, via its WSGI wrapping,
# cloud/api/lambda_function.py). Enum fields are checked against the real
# categories (core.MODEL_GROUPS / core.CRITICALITY_MAP / core.SIZE_TIERS)
# rather than a hand-copied list, so these tests can't silently drift out
# of sync with the actual trained models' categories.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_body", [None, "a string", ["a", "list"], 42, 3.14])
def test_run_predict_rejects_non_dict_body(bad_body):
    with pytest.raises(core.InputValidationError):
        core.run_predict(bad_body)


def test_run_predict_rejects_empty_body_naming_every_missing_field():
    with pytest.raises(core.InputValidationError) as excinfo:
        core.run_predict({})
    joined = " ".join(excinfo.value.errors)
    for field in ("model_grp", "age_days", "criticality_tier", "size_tier"):
        assert field in joined


@pytest.mark.parametrize("field,bad_value", [
    ("model_grp", "NOT_A_REAL_DRIVE_MODEL"),
    ("criticality_tier", "ultra"),
    ("size_tier", "xlarge"),
    ("which_model", "gpt4"),
])
def test_run_predict_rejects_unknown_enum_values(field, bad_value):
    payload = dict(GOLDEN_PAYLOAD, **{field: bad_value})
    with pytest.raises(core.InputValidationError) as excinfo:
        core.run_predict(payload)
    assert field in excinfo.value.errors[0]


@pytest.mark.parametrize("bad_age", [
    -1, -0.5, 999_999, float("nan"), float("inf"), float("-inf"), "not-a-number", None, [1, 2],
])
def test_run_predict_rejects_bad_age_days(bad_age):
    payload = dict(GOLDEN_PAYLOAD, age_days=bad_age)
    with pytest.raises(core.InputValidationError):
        core.run_predict(payload)


def test_run_predict_accepts_extra_unknown_fields():
    # a forward-compatible frontend sending an extra field (e.g. future
    # telemetry) shouldn't break the request -- only the fields the schema
    # actually declares are validated.
    payload = dict(GOLDEN_PAYLOAD, some_future_field="ignored")
    result = core.run_predict(payload)
    assert result["model_used"] == "Calibrated HistGBM"


def test_run_predict_which_model_defaults_to_histgbm():
    payload = {k: v for k, v in GOLDEN_PAYLOAD.items() if k != "which_model"}
    result = core.run_predict(payload)
    assert result["model_used"] == "Calibrated HistGBM"


# ---------------------------------------------------------------------------
# Structured logging (task 45) -- run_predict() emits one JSON log line per
# call (predict_served on success, predict_rejected on a validation
# failure) via Python's stdlib logging, which both deployments already
# capture for free (CloudWatch ingests a Lambda's stdout automatically;
# Render's log viewer shows stdout directly) -- see core.py's _log_event.
# ---------------------------------------------------------------------------
def test_run_predict_logs_one_structured_json_line_on_success(capsys):
    core.run_predict(GOLDEN_PAYLOAD)
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1, f"expected exactly one log line, got {out!r}"
    record = json.loads(out[0])
    assert record["event"] == "predict_served"
    assert record["model_grp"] == GOLDEN_PAYLOAD["model_grp"]
    assert record["which_model"] == GOLDEN_PAYLOAD["which_model"]
    assert isinstance(record["p_fail_within_window"], float)
    assert isinstance(record["duration_ms"], float)
    assert record["duration_ms"] >= 0


def test_run_predict_logs_one_structured_json_line_on_rejection(capsys):
    with pytest.raises(core.InputValidationError):
        core.run_predict({})
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1, f"expected exactly one log line, got {out!r}"
    record = json.loads(out[0])
    assert record["event"] == "predict_rejected"
    assert isinstance(record["errors"], list)
    assert len(record["errors"]) > 0


def test_run_predict_valid_request_unaffected_by_validation():
    # validation should be transparent to a well-formed request -- an int
    # age_days (as the golden payload uses) and the equivalent float must
    # produce identical predictions.
    result_int = core.run_predict(GOLDEN_PAYLOAD)
    result_float = core.run_predict(dict(GOLDEN_PAYLOAD, age_days=900.0))
    assert result_int["p_fail_within_window"] == result_float["p_fail_within_window"]
    assert result_int["expected_ttf_days"] == result_float["expected_ttf_days"]


# --------------------------------------------------------------------------- v2 ensemble
v2 = pytest.mark.skipif(core.V2 is None, reason="models/v2_ensemble not installed")


@v2
def test_v2_meta_and_prediction_shape():
    meta = core.get_meta()["v2"]
    assert meta["n_members"] == 20 and meta["default_drive_model"] in meta["drive_models"]
    r = core.run_predict({"which_model": "v2", "drive_model": meta["default_drive_model"], "age_days": 900,
                          "criticality_tier": "high", "size_tier": "medium"})
    lo, hi = r["p_interval_5_95"]
    assert 0 <= lo <= r["p_fail_within_window"] <= hi <= 1
    assert set(r) >= {"cost_sensitive", "threshold", "costs", "assumptions"}


@v2
def test_v2_risk_rises_with_bad_smart_counters():
    base = {"which_model": "v2", "drive_model": core.get_meta()["v2"]["default_drive_model"], "age_days": 900,
            "criticality_tier": "high", "size_tier": "medium"}
    healthy = core.run_predict(base)["p_fail_within_window"]
    failing = core.run_predict({**base, "s5": 240, "s197": 24, "s198": 24, "s187": 4, "trend": "rising"})
    assert failing["p_fail_within_window"] > 50 * healthy
    assert failing["cost_sensitive"]["migrate"] and failing["threshold"]["migrate"]


@v2
def test_v2_criticality_changes_the_cost_sensitive_decision_only():
    """8 pending sectors: p is a few percent, above tau, so the threshold always migrates; the
    cost-sensitive rule migrates a high-criticality VM and leaves a low-criticality one."""
    base = {"which_model": "v2", "drive_model": core.get_meta()["v2"]["default_drive_model"], "age_days": 900,
            "size_tier": "medium", "s197": 8}
    hi = core.run_predict({**base, "criticality_tier": "high"})
    lo = core.run_predict({**base, "criticality_tier": "low"})
    assert hi["threshold"]["migrate"] and lo["threshold"]["migrate"]
    assert hi["cost_sensitive"]["migrate"] and not lo["cost_sensitive"]["migrate"]


@v2
@pytest.mark.parametrize("bad", [{"drive_model": "NOPE"}, {"s5": -1}, {"trend": "falling"}, {"temp": 500}])
def test_v2_rejects_bad_input(bad):
    body = {"which_model": "v2", "drive_model": core.get_meta()["v2"]["default_drive_model"], "age_days": 900,
            "criticality_tier": "high", "size_tier": "medium", **bad}
    with pytest.raises(core.InputValidationError):
        core.run_predict(body)
