"""
Task 3 -- Failure probability model.

The Backblaze table gives one row per drive: final age (days) and whether
that final event was a real failure or a censoring (drive removed/observation
ended while still healthy). That is a survival-analysis setup, not a plain
classification table, so training a classifier directly on
(model, capacity, age) -> failed would leak the future (a drive's *final*
age is only known once we already know its outcome).

Fix: expand each drive into "person-period" rows -- one row per 30-day
interval the drive is known to have survived through, with a 0/1 label for
whether it failed during that specific interval. This is the standard
discrete-time hazard model construction and lets us train an ordinary
classifier to output h(t) = P(fail in this 30-day interval | survived to
the start of it) using only information available at the start of the
interval. Chaining h(t) forward gives P(failure within any lookahead
window), which is what the mitigation policy (task 6) actually needs.

Run from the project root: python3 scripts/02_failure_probability_model.py
"""
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import joblib

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)

BIN_DAYS = 30
TOP_N_MODELS = 15
LOOKAHEAD_DAYS = 30  # the P(failure) horizon the mitigation policy will consume

# ---------------------------------------------------------------------------
# 1. Load and build the person-period (discrete-time hazard) table
# ---------------------------------------------------------------------------
drv = pd.read_csv(PROCESSED / "backblaze_drives_clean.csv").dropna(subset=["age_days"]).reset_index(drop=True)
drv["drive_idx"] = np.arange(len(drv))

top_models = drv["model"].value_counts().head(TOP_N_MODELS).index.tolist()
drv["model_grp"] = np.where(drv["model"].isin(top_models), drv["model"], "OTHER")

print(f"Drives: {len(drv):,} | modeled model groups: {len(top_models)} + OTHER")

def build_person_period(df, bin_days=BIN_DAYS):
    """One row per (drive, bin) it survived through; label=1 only on the bin
    containing its failure, 0 otherwise. Censored drives contribute only 0s."""
    n_bins = np.ceil(df["age_days"].values / bin_days).astype(int)
    n_bins = np.maximum(n_bins, 1)
    rows = []
    for drive_idx, model_grp, capacity_tb, failed, nb in zip(
        df["drive_idx"], df["model_grp"], df["capacity_tb"], df["failed"], n_bins
    ):
        bin_idx = np.arange(nb)
        label = np.zeros(nb, dtype=int)
        if failed == 1:
            label[-1] = 1
        rows.append(pd.DataFrame({
            "drive_idx": drive_idx,
            "model_grp": model_grp,
            "capacity_tb": capacity_tb,
            "bin_idx": bin_idx,
            "bin_start_days": bin_idx * bin_days,
            "event": label,
        }))
    return pd.concat(rows, ignore_index=True)

pp = build_person_period(drv)
print(f"Person-period rows: {len(pp):,} (from {len(drv):,} drives), "
      f"positive rate: {pp['event'].mean():.4%}")

# ---------------------------------------------------------------------------
# 2. Drive-level train/test split (never split a drive's own bins across sets)
# ---------------------------------------------------------------------------
gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
train_idx, test_idx = next(gss.split(pp, groups=pp["drive_idx"]))
pp_train, pp_test = pp.iloc[train_idx], pp.iloc[test_idx]
print(f"Train rows: {len(pp_train):,} | Test rows: {len(pp_test):,}")

FEATURES = ["model_grp", "capacity_tb", "bin_start_days"]
X_train, y_train = pp_train[FEATURES], pp_train["event"]
X_test, y_test = pp_test[FEATURES], pp_test["event"]

preprocess = ColumnTransformer([
    ("model_ohe", OneHotEncoder(handle_unknown="ignore"), ["model_grp"]),
], remainder="passthrough")

# ---------------------------------------------------------------------------
# 3. Two candidate models: interpretable logistic hazard vs. nonlinear GBM
# ---------------------------------------------------------------------------
# NOTE: no class_weight="balanced" here. The mitigation policy (task 6) will
# multiply this probability directly into an expected-cost calculation, so it
# must be a calibrated probability, not just a good ranking score -- balanced
# class weights inflate the minority-class probability scale and would silently
# break that downstream math even though ROC-AUC looks fine either way.
logit = Pipeline([
    ("prep", preprocess),
    ("clf", LogisticRegression(max_iter=2000)),
])
logit.fit(X_train, y_train)

gbm = HistGradientBoostingClassifier(
    categorical_features=[0], max_iter=200, learning_rate=0.08,
    random_state=42,
)
# HGB wants the categorical column as a plain category dtype, not one-hot.
X_train_gbm = X_train.copy(); X_train_gbm["model_grp"] = X_train_gbm["model_grp"].astype("category")
X_test_gbm = X_test.copy(); X_test_gbm["model_grp"] = X_test_gbm["model_grp"].astype("category")
gbm.fit(X_train_gbm, y_train)

def evaluate(name, y_true, y_prob):
    auc = roc_auc_score(y_true, y_prob)
    ap = average_precision_score(y_true, y_prob)
    brier = brier_score_loss(y_true, y_prob)
    print(f"{name:>22s} | ROC-AUC={auc:.4f}  PR-AUC={ap:.4f}  Brier={brier:.5f}")
    return auc, ap, brier

print("\n--- Held-out person-period evaluation (per 30-day bin) ---")
p_logit = logit.predict_proba(X_test)[:, 1]
p_gbm = gbm.predict_proba(X_test_gbm)[:, 1]
evaluate("Logistic hazard", y_test, p_logit)
evaluate("HistGBM hazard", y_test, p_gbm)

# Calibration check: predicted vs. empirical hazard by decile of predicted risk
calib = pd.DataFrame({"y": y_test.values, "p": p_gbm})
calib["decile"] = pd.qcut(calib["p"], 10, duplicates="drop")
calib_table = calib.groupby("decile", observed=True).agg(
    n=("y", "size"), mean_predicted=("p", "mean"), empirical_rate=("y", "mean")
)
print("\nCalibration by predicted-risk decile (HistGBM):\n", calib_table)

best_model, best_name = (gbm, "histgbm") if average_precision_score(y_test, p_gbm) >= average_precision_score(y_test, p_logit) else (logit, "logistic")
print(f"\nSelected model for downstream use: {best_name}")

# ---------------------------------------------------------------------------
# 4. Build a per-(model_grp, age_bucket) hazard + P(fail within window) lookup
#    -- this is what the cheap replay simulator (task 8) will actually query,
#    so it doesn't need sklearn at simulation time.
# ---------------------------------------------------------------------------
age_bucket_edges = np.arange(0, drv["age_days"].max() + BIN_DAYS, BIN_DAYS)
lookup_rows = []
groups = top_models + ["OTHER"]
capacity_by_group = drv.groupby("model_grp")["capacity_tb"].median()

for grp in groups:
    cap = capacity_by_group.get(grp, drv["capacity_tb"].median())
    grid = pd.DataFrame({
        "model_grp": grp,
        "capacity_tb": cap,
        "bin_start_days": age_bucket_edges,
    })
    if best_name == "histgbm":
        grid_in = grid.copy(); grid_in["model_grp"] = grid_in["model_grp"].astype("category")
        # align categories with training set so unseen-category doesn't break predict
        grid_in["model_grp"] = grid_in["model_grp"].cat.set_categories(X_train_gbm["model_grp"].cat.categories)
        hazard = best_model.predict_proba(grid_in[FEATURES])[:, 1]
    else:
        hazard = best_model.predict_proba(grid[FEATURES])[:, 1]
    grid["hazard_30d"] = hazard
    # P(fail within LOOKAHEAD_DAYS | survived to bin_start) via chained hazard
    n_steps = max(1, LOOKAHEAD_DAYS // BIN_DAYS)
    surv = np.ones(len(grid))
    p_fail_window = np.zeros(len(grid))
    haz = grid["hazard_30d"].values
    for i in range(len(grid)):
        s = 1.0
        for k in range(n_steps):
            j = i + k
            if j >= len(grid):
                break
            s *= (1 - haz[j])
        p_fail_window[i] = 1 - s
    grid["p_fail_within_window"] = p_fail_window
    lookup_rows.append(grid)

hazard_lookup = pd.concat(lookup_rows, ignore_index=True)
hazard_lookup.to_csv(PROCESSED / "hazard_lookup_table.csv", index=False)
joblib.dump({"model": best_model, "model_name": best_name, "features": FEATURES,
             "bin_days": BIN_DAYS, "lookahead_days": LOOKAHEAD_DAYS,
             "train_categories": list(X_train_gbm["model_grp"].cat.categories)},
            MODELS_DIR / "failure_probability_model.joblib")

print(f"\nSaved -> data/processed/hazard_lookup_table.csv "
      f"({len(hazard_lookup):,} rows, {len(groups)} model groups x {len(age_bucket_edges)} age bins)")
print(f"Saved -> models/failure_probability_model.joblib")
print("\nDone.")
