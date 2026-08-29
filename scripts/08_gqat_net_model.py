"""
Task 11 -- train the GQAT-Net-inspired NumPy model on the same discrete-time
hazard problem as 02_failure_probability_model.py, and compare it head-to-head
against that script's calibrated HistGradientBoostingClassifier on IDENTICAL
held-out rows.

This deliberately rebuilds the exact same person-period table and the exact
same GroupShuffleSplit(random_state=42) drive-level train/test split as
02_failure_probability_model.py, so "GQAT-Net vs. HistGBM" is a fair,
apples-to-apples comparison on the same test set -- not two different
data slices.

Compute-budget notes (read before assuming the numbers below are "the real"
GQAT-Net paper's numbers -- they are not; see task11_summary.md):
  - This sandbox has 2 CPU cores and no deep-learning framework, so training
    runs a hand-written NumPy forward/backward pass (see gqat_net_numpy.py),
    not a GPU-accelerated Keras model.
  - The full person-period table is ~3.46M rows; training subsamples the
    negatives (all positives are kept) to keep one epoch's compute bounded,
    then applies SMOTE (hand-rolled -- imbalanced-learn is also unavailable)
    to rebalance the *training* fold only. Evaluation uses the FULL,
    untouched, naturally-imbalanced test fold, exactly like 02's evaluation.
"""
import time
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import GroupShuffleSplit
from sklearn.model_selection import train_test_split
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from sklearn.isotonic import IsotonicRegression
from sklearn.preprocessing import MinMaxScaler
import joblib

from gqat_net_numpy import GQATNetNumpy

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)

BIN_DAYS = 30
TOP_N_MODELS = 15
LOOKAHEAD_DAYS = 30
SEED = 42

TRAIN_NEG_SUBSAMPLE = 15_000   # negatives sampled from the training fold (compute budget: hand-written
                                # NumPy backprop on 2 CPU cores, no GPU/BLAS-fused framework)
VAL_FRACTION = 0.15
SMOTE_K = 5
SMOTE_TARGET_RATIO = 1.0       # 1.0 == balance minority up to match majority count (imblearn's default)
EPOCHS = 15
BATCH_SIZE = 512
LR = 2e-3
EVAL_CHUNK = 20_000             # inference batch size
TEST_EVAL_SAMPLE = 100_000      # random subsample of the (naturally-imbalanced) test fold for
                                 # evaluation speed -- ~200 real failure events at this sample size,
                                 # same compute-budget reasoning as the rest of this script

rng_np = np.random.default_rng(SEED)

# ---------------------------------------------------------------------------
# 1. Rebuild the exact same person-period table + split as script 02
# ---------------------------------------------------------------------------
drv = pd.read_csv(PROCESSED / "backblaze_drives_clean.csv").dropna(subset=["age_days"]).reset_index(drop=True)
drv["drive_idx"] = np.arange(len(drv))
top_models = drv["model"].value_counts().head(TOP_N_MODELS).index.tolist()
drv["model_grp"] = np.where(drv["model"].isin(top_models), drv["model"], "OTHER")

def build_person_period(df, bin_days=BIN_DAYS):
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
            "drive_idx": drive_idx, "model_grp": model_grp, "capacity_tb": capacity_tb,
            "bin_idx": bin_idx, "bin_start_days": bin_idx * bin_days, "event": label,
        }))
    return pd.concat(rows, ignore_index=True)

print("Rebuilding person-period table (identical construction to script 02)...")
pp = build_person_period(drv)
print(f"Person-period rows: {len(pp):,}, positive rate: {pp['event'].mean():.4%}")

gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
train_idx, test_idx = next(gss.split(pp, groups=pp["drive_idx"]))
pp_train, pp_test_all = pp.iloc[train_idx].copy(), pp.iloc[test_idx].copy()
print(f"Train rows: {len(pp_train):,} | Test rows (full): {len(pp_test_all):,}  (same split as script 02)")

# Evaluation subsample of the (naturally-imbalanced) test fold, purely for inference
# speed on hand-written NumPy forward passes -- both models are scored on these
# exact same rows, so the comparison stays fair even though it isn't the full fold.
if TEST_EVAL_SAMPLE < len(pp_test_all):
    eval_pos = rng_np.choice(len(pp_test_all), size=TEST_EVAL_SAMPLE, replace=False)
    pp_test = pp_test_all.iloc[eval_pos].reset_index(drop=True)
else:
    pp_test = pp_test_all.reset_index(drop=True)
print(f"Test rows (evaluation subsample, both models scored on these): {len(pp_test):,}, "
      f"positive rate: {pp_test['event'].mean():.4%}")

# ---------------------------------------------------------------------------
# 2. Feature engineering -- a richer feature set than the 3-feature HistGBM
#    model, giving the sequence-based architecture something to attend over.
#    model_hist_hazard is a target encoding fit on the TRAINING fold only.
# ---------------------------------------------------------------------------
model_order = sorted(pp_train["model_grp"].unique())
model_code = {m: i for i, m in enumerate(model_order)}
model_hazard = pp_train.groupby("model_grp")["event"].mean().to_dict()
global_hazard = pp_train["event"].mean()
capacity_median_by_model = pp_train.groupby("model_grp")["capacity_tb"].median().to_dict()

def engineer(df):
    out = pd.DataFrame(index=df.index)
    out["capacity_tb"] = df["capacity_tb"]
    out["bin_start_days"] = df["bin_start_days"]
    out["bin_idx"] = df["bin_idx"]
    out["age_years"] = df["bin_start_days"] / 365.0
    out["log1p_bin_start"] = np.log1p(df["bin_start_days"])
    out["bin_start_sq_norm"] = (df["bin_start_days"] ** 2) / 1e6
    out["model_code"] = df["model_grp"].map(model_code).fillna(-1)
    out["model_hist_hazard"] = df["model_grp"].map(model_hazard).fillna(global_hazard)
    out["is_new_drive"] = (df["bin_idx"] == 0).astype(float)
    out["capacity_x_bin"] = df["capacity_tb"] * df["bin_start_days"] / 1000.0
    out["capacity_vs_model_median"] = df["capacity_tb"] - df["model_grp"].map(capacity_median_by_model).fillna(df["capacity_tb"].median())
    return out

FEATURES = ["capacity_tb", "bin_start_days", "bin_idx", "age_years", "log1p_bin_start",
            "bin_start_sq_norm", "model_code", "model_hist_hazard", "is_new_drive",
            "capacity_x_bin", "capacity_vs_model_median"]

X_train_full = engineer(pp_train)[FEATURES].values.astype(np.float64)
y_train_full = pp_train["event"].values.astype(np.float64)
X_test_full = engineer(pp_test)[FEATURES].values.astype(np.float64)
y_test_full = pp_test["event"].values.astype(np.float64)

# ---------------------------------------------------------------------------
# 3. Compute-budget subsample of the TRAINING fold only (all positives kept)
# ---------------------------------------------------------------------------
pos_idx = np.where(y_train_full == 1)[0]
neg_idx = np.where(y_train_full == 0)[0]
neg_sample = rng_np.choice(neg_idx, size=min(TRAIN_NEG_SUBSAMPLE, len(neg_idx)), replace=False)
sub_idx = np.concatenate([pos_idx, neg_sample])
rng_np.shuffle(sub_idx)
X_sub, y_sub = X_train_full[sub_idx], y_train_full[sub_idx]
print(f"Training subsample: {len(X_sub):,} rows ({int(y_sub.sum())} positives, "
      f"{len(X_sub) - int(y_sub.sum())} negatives)")

X_tr, X_val, y_tr, y_val = train_test_split(
    X_sub, y_sub, test_size=VAL_FRACTION, stratify=y_sub, random_state=SEED
)

# Scale AFTER the train/val split, fit on train only (no leakage)
scaler = MinMaxScaler()
X_tr_scaled = scaler.fit_transform(X_tr)
X_val_scaled = scaler.transform(X_val)
X_test_scaled = scaler.transform(X_test_full)

# ---------------------------------------------------------------------------
# 4. Hand-rolled SMOTE (imbalanced-learn is unavailable in this sandbox --
#    same constraint as the deep-learning framework; see task11_summary.md).
#    Standard k-NN interpolation between minority-class points, computed with
#    scikit-learn's NearestNeighbors (which IS available).
# ---------------------------------------------------------------------------
def manual_smote(X, y, k=SMOTE_K, target_ratio=SMOTE_TARGET_RATIO, seed=SEED):
    rng = np.random.default_rng(seed)
    X_min = X[y == 1]
    n_min, n_maj = len(X_min), int((y == 0).sum())
    n_needed = int(n_maj * target_ratio) - n_min
    if n_needed <= 0 or n_min < 2:
        return X, y
    k_eff = min(k, n_min - 1)
    nn = NearestNeighbors(n_neighbors=k_eff + 1).fit(X_min)
    _, neighbor_idx = nn.kneighbors(X_min)
    base = rng.integers(0, n_min, size=n_needed)
    partner_choice = rng.integers(1, k_eff + 1, size=n_needed)  # skip index 0 (self)
    partners = neighbor_idx[base, partner_choice]
    lam = rng.random(size=(n_needed, 1))
    synth = X_min[base] + lam * (X_min[partners] - X_min[base])
    X_new = np.vstack([X, synth])
    y_new = np.concatenate([y, np.ones(n_needed)])
    perm = rng.permutation(len(X_new))
    return X_new[perm], y_new[perm]

t0 = time.time()
X_tr_sm, y_tr_sm = manual_smote(X_tr_scaled, y_tr)
print(f"SMOTE: {len(X_tr_scaled):,} -> {len(X_tr_sm):,} training rows "
      f"({y_tr_sm.mean():.1%} positive) in {time.time() - t0:.1f}s")

# ---------------------------------------------------------------------------
# 5. Train
# ---------------------------------------------------------------------------
model = GQATNetNumpy(n_features=len(FEATURES), seed=SEED)
print(f"\nTraining GQAT-Net-inspired model on {len(X_tr_sm):,} rows "
      f"({len(FEATURES)} engineered features)...")
t0 = time.time()
history = model.fit(X_tr_sm, y_tr_sm, epochs=EPOCHS, batch_size=BATCH_SIZE, lr=LR,
                     X_val=X_val_scaled, y_val=y_val, patience=4, seed=SEED)
train_time = time.time() - t0
print(f"Training time: {train_time:.1f}s ({train_time/len(history):.1f}s/epoch avg)")

# ---------------------------------------------------------------------------
# 6. Isotonic calibration on the (untouched, imbalanced) validation fold --
#    exactly the fix this project used for the class-imbalance/calibration
#    tension in task 3, and exactly what the original GQAT-Net code does.
# ---------------------------------------------------------------------------
p_val_raw = model.predict_proba(X_val_scaled)
iso = IsotonicRegression(out_of_bounds="clip")
iso.fit(p_val_raw, y_val)

# ---------------------------------------------------------------------------
# 7. Evaluate on the FULL, untouched, naturally-imbalanced test fold, in
#    chunks (attention/conv intermediates would otherwise blow up memory
#    across ~690K rows at once).
# ---------------------------------------------------------------------------
print(f"\nRunning inference on the full held-out test fold ({len(X_test_scaled):,} rows)...")
t0 = time.time()
p_test_raw = np.concatenate([
    model.predict_proba(X_test_scaled[i:i + EVAL_CHUNK])
    for i in range(0, len(X_test_scaled), EVAL_CHUNK)
])
inf_time = time.time() - t0
p_test_cal = iso.predict(p_test_raw)
print(f"Inference time: {inf_time:.1f}s ({1000*inf_time/len(X_test_scaled):.3f} ms/row)")

def ece(y_true, y_prob, n_bins=10):
    bins = np.linspace(0, 1, n_bins + 1)
    ids = np.digitize(y_prob, bins) - 1
    total = 0.0
    for b in range(n_bins):
        m = ids == b
        if not np.any(m):
            continue
        total += m.mean() * abs(y_true[m].mean() - y_prob[m].mean())
    return total

def report(name, y_true, y_prob):
    auc = roc_auc_score(y_true, y_prob)
    ap = average_precision_score(y_true, y_prob)
    brier = brier_score_loss(y_true, y_prob)
    e = ece(y_true, y_prob)
    print(f"{name:38s} ROC-AUC={auc:.4f}  PR-AUC={ap:.4f}  Brier={brier:.5f}  ECE={e:.5f}")
    return dict(model=name, roc_auc=auc, pr_auc=ap, brier=brier, ece=e)

print("\n--- Held-out test-fold evaluation (identical rows for both models) ---")
results = []
results.append(report("GQAT-Net-inspired (raw)", y_test_full, p_test_raw))
results.append(report("GQAT-Net-inspired (isotonic-calibrated)", y_test_full, p_test_cal))

hgb_bundle = joblib.load(MODELS_DIR / "failure_probability_model.joblib")
hgb_model, hgb_name = hgb_bundle["model"], hgb_bundle["model_name"]
hgb_feats = hgb_bundle["features"]
X_test_hgb = pp_test[["model_grp", "capacity_tb", "bin_start_days"]].copy()
if hgb_name == "histgbm":
    X_test_hgb["model_grp"] = X_test_hgb["model_grp"].astype("category")
    X_test_hgb["model_grp"] = X_test_hgb["model_grp"].cat.set_categories(hgb_bundle["train_categories"])
p_test_hgb = hgb_model.predict_proba(X_test_hgb[hgb_feats])[:, 1]
results.append(report(f"Existing calibrated {hgb_name} (task 3)", y_test_full, p_test_hgb))

# MC-dropout uncertainty on a small sample of the test set (illustrative -- the
# per-row std is what the web demo surfaces as a confidence indicator)
mc_sample = X_test_scaled[:2000]
mc_mean, mc_std = model.predict_proba_mc(mc_sample, n_iter=20)
print(f"\nMC-dropout on {len(mc_sample):,} test rows: mean predicted-prob std across "
      f"20 stochastic passes = {mc_std.mean():.5f} (min={mc_std.min():.5f}, max={mc_std.max():.5f})")

pd.DataFrame(results).to_csv(PROCESSED / "gqat_net_vs_histgbm_comparison.csv", index=False)

# ---------------------------------------------------------------------------
# 8. Save everything the web demo will need to run this model live
# ---------------------------------------------------------------------------
model.clear_cache()  # drop the last forward pass's cached activations before pickling --
                      # otherwise joblib serializes tens/hundreds of MB of intermediate
                      # tensors sized to whatever batch happened to run last, none of
                      # which predict_proba() needs (each call rebuilds its own cache).
joblib.dump({
    "model": model, "scaler": scaler, "isotonic": iso, "features": FEATURES,
    "model_code": model_code, "model_hazard": model_hazard, "global_hazard": global_hazard,
    "capacity_median_by_model": capacity_median_by_model, "bin_days": BIN_DAYS,
    "lookahead_days": LOOKAHEAD_DAYS, "train_time_s": train_time,
}, MODELS_DIR / "gqat_net_numpy_model.joblib")
print(f"\nSaved -> models/gqat_net_numpy_model.joblib")
print(f"Saved -> data/processed/gqat_net_vs_histgbm_comparison.csv")
print("\nDone.")
