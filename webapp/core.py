"""
Core inference/decision logic for the live demo -- factored out of app.py so
the exact same tested code backs BOTH deployment targets:
  1. webapp/app.py        -- traditional Flask server (Render, or `python3
                              app.py` locally), renders the full HTML page.
  2. cloud/api/lambda_function.py -- AWS Lambda (container image) behind API
                              Gateway, serving JSON only (/api/meta,
                              /api/predict) for the static S3+CloudFront
                              frontend in cloud/frontend/.
No business logic lives in either entrypoint -- both just call into this
module -- so there is no risk of the two deployments silently drifting apart,
the same principle scripts/policy.py already applies to the two policies.
"""
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PROCESSED = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"
FIGURES = ROOT / "docs" / "figures"

sys.path.insert(0, str(SCRIPTS))
import policy  # noqa: E402  (scripts/policy.py -- the actual decision-rule module used everywhere else)
import gqat_net_numpy  # noqa: E402,F401  (registers the class so joblib can unpickle the saved model)

# ---------------------------------------------------------------------------
# Load everything once per process (once per Lambda container on cold start,
# once at process start for the traditional server)
# ---------------------------------------------------------------------------
print("Loading models and reference data...")
HGB_BUNDLE = joblib.load(MODELS_DIR / "failure_probability_model.joblib")
GQAT_BUNDLE = joblib.load(MODELS_DIR / "gqat_net_numpy_model.joblib")
HAZARD_LOOKUP = pd.read_csv(PROCESSED / "hazard_lookup_table.csv")
COMPARISON = pd.read_csv(PROCESSED / "gqat_net_vs_histgbm_comparison.csv")
HEADLINE = pd.read_csv(PROCESSED / "simulation_headline_summary.csv", index_col=0)
CORR_SWEEP = pd.read_csv(PROCESSED / "correlated_assignment_sweep.csv")

BIN_DAYS = int(HGB_BUNDLE["bin_days"])
LOOKAHEAD_DAYS = int(HGB_BUNDLE["lookahead_days"])
TAIL_EXTRA_BINS = 200
MAX_AGE_DAYS = 3000

# 95th-percentile-of-real-host-risk threshold, computed live from the same
# lookup table and the same method as 05_policy_design.py.
TAU_DEFAULT = float(HAZARD_LOOKUP["p_fail_within_window"].quantile(0.95))

MODEL_GROUPS = sorted(GQAT_BUNDLE["model_code"].keys())  # the exact TOP_N_MODELS groups both models were trained on
CAPACITY_BY_MODEL = GQAT_BUNDLE["capacity_median_by_model"]

CRITICALITY_MAP = {  # identical to scripts/01_preprocess.py
    "high": 1.0, "medium": 0.6, "low": 0.3,
}
UNMITIGATED_FAILURE_DOWNTIME_MIN = 10  # scripts/04_workload_criticality_cost.py
MIGRATION_BANDWIDTH_MBPS = 1250
MAX_DIRTY_RATE_MBPS_AT_100PCT_CPU = 150
STOPCOPY_FALLBACK_S = 60
BASE_BLACKOUT_S = 1.0

# Precomputed from data/processed/azure_vms_with_costs.csv.gz (a 198MB Git-LFS
# file we don't want a deployed web app loading into memory just to read 3
# median values). Regenerate via:
#   VM_COSTS.groupby("size_tier")[["memory_gb","vcores","avg_cpu"]].median().round(2)
with open(PROCESSED / "size_tier_profile.json") as _f:
    SIZE_TIER_PROFILE = json.load(_f)
SIZE_TIERS = sorted(SIZE_TIER_PROFILE.keys())  # real categories only (the Azure data has no "xlarge")

print(f"Loaded. {len(MODEL_GROUPS)} drive model groups, tau_default={TAU_DEFAULT:.5f}, "
      f"size-tier profiles: {SIZE_TIER_PROFILE}")


# ---------------------------------------------------------------------------
# Live failure-probability hazard curves (one model call per request -- this
# is genuinely running the trained model, not looking up a precomputed table)
# ---------------------------------------------------------------------------
def _bin_grid():
    n_real_bins = MAX_AGE_DAYS // BIN_DAYS
    return np.arange(n_real_bins + TAIL_EXTRA_BINS) * BIN_DAYS


def hazard_curve_histgbm(model_grp, capacity_tb):
    bins = _bin_grid()
    grid = pd.DataFrame({"model_grp": model_grp, "capacity_tb": capacity_tb, "bin_start_days": bins})
    grid["model_grp"] = grid["model_grp"].astype("category").cat.set_categories(HGB_BUNDLE["train_categories"])
    haz = HGB_BUNDLE["model"].predict_proba(grid[HGB_BUNDLE["features"]])[:, 1]
    # extrapolate the tail at the last *real* bin's hazard (matches 03_time_to_failure.py's approach)
    n_real = MAX_AGE_DAYS // BIN_DAYS
    haz[n_real:] = haz[n_real - 1]
    return bins, haz, None  # (bins, hazard, mc_std)


def hazard_curve_gqat(model_grp, capacity_tb):
    bins = _bin_grid()
    n = len(bins)
    df = pd.DataFrame({"capacity_tb": capacity_tb, "bin_start_days": bins})
    df["bin_idx"] = (df["bin_start_days"] / BIN_DAYS).astype(int)
    df["age_years"] = df["bin_start_days"] / 365.0
    df["log1p_bin_start"] = np.log1p(df["bin_start_days"])
    df["bin_start_sq_norm"] = (df["bin_start_days"] ** 2) / 1e6
    df["model_code"] = GQAT_BUNDLE["model_code"].get(model_grp, -1)
    df["model_hist_hazard"] = GQAT_BUNDLE["model_hazard"].get(model_grp, GQAT_BUNDLE["global_hazard"])
    df["is_new_drive"] = (df["bin_idx"] == 0).astype(float)
    df["capacity_x_bin"] = df["capacity_tb"] * df["bin_start_days"] / 1000.0
    df["capacity_vs_model_median"] = capacity_tb - CAPACITY_BY_MODEL.get(model_grp, capacity_tb)
    X = df[GQAT_BUNDLE["features"]].values.astype(np.float64)
    Xs = GQAT_BUNDLE["scaler"].transform(X)
    p_raw = GQAT_BUNDLE["model"].predict_proba(Xs)
    haz = GQAT_BUNDLE["isotonic"].predict(p_raw)
    n_real = MAX_AGE_DAYS // BIN_DAYS
    haz[n_real:] = haz[n_real - 1]
    # MC-dropout uncertainty, only around the bins near the requested age (cheap: <=20 rows)
    mc_mean, mc_std = GQAT_BUNDLE["model"].predict_proba_mc(Xs[:min(60, n)], n_iter=15)
    return bins, haz, mc_std


def survival_and_ttf(bins, hazard, start_idx):
    """Same method as scripts/03_time_to_failure.py: chained survival from the
    current age forward, expected TTF via trapezoidal integration, median TTF
    via linear interpolation across the bin where survival crosses 0.5."""
    haz_fwd = hazard[start_idx:]
    surv = np.cumprod(1 - haz_fwd)
    surv_full = np.concatenate([[1.0], surv])
    t_days = np.arange(len(surv_full)) * BIN_DAYS
    expected_ttf = float(np.trapezoid(surv_full, t_days))

    median_ttf = None
    below = np.where(surv_full <= 0.5)[0]
    if len(below) > 0:
        i = below[0]
        if i == 0:
            median_ttf = 0.0
        else:
            s0, s1 = surv_full[i - 1], surv_full[i]
            t0, t1 = t_days[i - 1], t_days[i]
            frac = (s0 - 0.5) / (s0 - s1) if s0 != s1 else 0.0
            median_ttf = float(t0 + frac * (t1 - t0))

    n_steps = max(1, LOOKAHEAD_DAYS // BIN_DAYS)
    p_fail_within_window = float(1 - np.prod(1 - hazard[start_idx:start_idx + n_steps]))
    return expected_ttf, median_ttf, p_fail_within_window


# ---------------------------------------------------------------------------
# Migration cost -- the exact Clark et al. pre-copy formula from
# scripts/04_workload_criticality_cost.py, computed live from the chosen
# size tier's real median memory/vCPU/CPU-utilization.
# ---------------------------------------------------------------------------
def migration_and_failure_cost(size_tier, criticality_tier):
    prof = SIZE_TIER_PROFILE[size_tier]
    memory_gb, avg_cpu = prof["memory_gb"], prof["avg_cpu"]
    crit_w = CRITICALITY_MAP[criticality_tier]

    memory_mb = memory_gb * 1024
    dirty_rate_mbps = (avg_cpu / 100.0) * MAX_DIRTY_RATE_MBPS_AT_100PCT_CPU
    converges = dirty_rate_mbps < 0.9 * MIGRATION_BANDWIDTH_MBPS
    if converges:
        migration_time_s = memory_mb / (MIGRATION_BANDWIDTH_MBPS - dirty_rate_mbps)
        blackout_s = BASE_BLACKOUT_S
    else:
        migration_time_s = STOPCOPY_FALLBACK_S
        blackout_s = STOPCOPY_FALLBACK_S

    migration_customer_cost_min = (blackout_s / 60.0) * crit_w
    migration_resource_cost_min = migration_time_s / 60.0
    total_migration_cost_min = migration_customer_cost_min + migration_resource_cost_min
    failure_customer_cost_min = UNMITIGATED_FAILURE_DOWNTIME_MIN * crit_w

    return {
        "precopy_converges": bool(converges),
        "migration_time_s": round(migration_time_s, 2),
        "migration_blackout_s": round(blackout_s, 2),
        "migration_resource_cost_min": round(migration_resource_cost_min, 4),
        "migration_customer_cost_min": round(migration_customer_cost_min, 4),
        "total_migration_cost_min": round(total_migration_cost_min, 4),
        "failure_customer_cost_min": round(failure_customer_cost_min, 4),
        "size_tier_profile": prof,
    }


# ---------------------------------------------------------------------------
# Request-shaped entry points, used directly by both app.py (Flask routes)
# and cloud/api/lambda_function.py.
# ---------------------------------------------------------------------------
def get_meta():
    """Everything the frontend needs to render its controls and the 'real
    findings' panel -- what app.py's `/` route used to hand to Jinja, now
    also servable as plain JSON for the static frontend."""
    return {
        "model_groups": MODEL_GROUPS,
        "size_tiers": SIZE_TIERS,
        "criticality_tiers": list(CRITICALITY_MAP.keys()),
        "tau_default": round(TAU_DEFAULT, 5),
        "headline": HEADLINE.T.to_dict("index"),
        "comparison": COMPARISON.to_dict("records"),
        "corr_sweep": CORR_SWEEP.to_dict("records"),
        "max_age_days": MAX_AGE_DAYS,
        "bin_days": BIN_DAYS,
        "lookahead_days": LOOKAHEAD_DAYS,
    }


def run_predict(body):
    """body: dict with model_grp, age_days, criticality_tier, size_tier,
    which_model. Returns a JSON-serializable dict -- the exact same shape
    /api/predict has always returned."""
    model_grp = body["model_grp"]
    age_days = float(body["age_days"])
    criticality_tier = body["criticality_tier"]
    size_tier = body["size_tier"]
    which_model = body.get("which_model", "histgbm")

    capacity_tb = CAPACITY_BY_MODEL.get(model_grp, 4.0)
    start_idx = int(min(age_days, MAX_AGE_DAYS - BIN_DAYS) // BIN_DAYS)

    mc_std_summary = None
    if which_model == "gqat":
        bins, hazard, mc_std = hazard_curve_gqat(model_grp, capacity_tb)
        if mc_std is not None and len(mc_std) > 0:
            mc_std_summary = float(np.mean(mc_std))
        model_label = "GQAT-Net-inspired (NumPy, isotonic-calibrated)"
    else:
        bins, hazard, _ = hazard_curve_histgbm(model_grp, capacity_tb)
        model_label = "Calibrated HistGBM (task 3)"

    expected_ttf, median_ttf, p_fail_window = survival_and_ttf(bins, hazard, start_idx)

    costs = migration_and_failure_cost(size_tier, criticality_tier)

    cs = policy.cost_sensitive_decision(
        p_fail_window, expected_ttf, costs["failure_customer_cost_min"], costs["total_migration_cost_min"],
        lookahead_days=LOOKAHEAD_DAYS,
    )
    th_migrate = bool(policy.threshold_decision(p_fail_window, TAU_DEFAULT))

    return {
        "model_used": model_label,
        "p_fail_within_window": p_fail_window,
        "expected_ttf_days": round(expected_ttf, 1),
        "median_ttf_days": round(median_ttf, 1) if median_ttf is not None else None,
        "mc_dropout_std": mc_std_summary,
        "capacity_tb_used": capacity_tb,
        "costs": costs,
        "cost_sensitive": {
            "migrate": bool(cs["migrate"]),
            "expected_cost_of_inaction": round(float(cs["expected_cost_of_inaction"]), 5),
            "migration_cost": round(float(costs["total_migration_cost_min"]), 5),
            "urgency_weight": round(float(cs["urgency_weight"]), 3),
        },
        "threshold": {
            "migrate": th_migrate,
            "tau": TAU_DEFAULT,
        },
    }
