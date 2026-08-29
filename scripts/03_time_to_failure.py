"""
Task 4 -- Time-to-failure (TTF) estimation.

This deliberately does NOT train a new model. Task 3's hazard lookup table
(P(fail in this 30-day bin | survived to it), per model group x age) already
implies a full survival curve S(t) = prod_{k<=t}(1 - hazard_k). TTF is just
composition on top of that survival curve:
  - median residual life  = smallest horizon at which S drops below 0.5
  - expected residual life = area under the (conditional) survival curve
This keeps task 3 and task 4 consistent by construction -- a policy that
uses both signals is reading two views of the same underlying model, not
two models that could disagree with each other.

Run from the project root: python3 scripts/03_time_to_failure.py
"""
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

BIN_DAYS = 30
TAIL_EXTRA_BINS = 200  # ~16 extra years of constant-hazard tail, see note below

hazard = pd.read_csv(PROCESSED / "hazard_lookup_table.csv").sort_values(
    ["model_grp", "bin_start_days"]
).reset_index(drop=True)

# ---------------------------------------------------------------------------
# 1. Extend each model group's hazard curve with a constant-hazard tail.
#    The Backblaze data only observes drives out to ~8 years (max bin ~2910
#    days); very few drives are observed that old, so any hazard estimate
#    near the edge is thin-sample and any *extrapolation* past it is
#    unsupported by data. Rather than silently trusting the model past its
#    training range, we explicitly assume the hazard holds constant at its
#    last-observed-bin value beyond that point. This is a standard, clearly-
#    stated way to make "expected residual life" finite and computable
#    without pretending we know what happens to 10-year-old drives -- it's
#    a documented assumption, not a hidden one.
# ---------------------------------------------------------------------------
rows = []
for grp, g in hazard.groupby("model_grp"):
    g = g.sort_values("bin_start_days").reset_index(drop=True)
    last_hazard = g["hazard_30d"].iloc[-1]
    last_bin = g["bin_start_days"].iloc[-1]
    tail = pd.DataFrame({
        "model_grp": grp,
        "capacity_tb": g["capacity_tb"].iloc[-1],
        "bin_start_days": last_bin + BIN_DAYS * np.arange(1, TAIL_EXTRA_BINS + 1),
        "hazard_30d": last_hazard,
        "p_fail_within_window": g["p_fail_within_window"].iloc[-1],
        "is_extrapolated_tail": True,
    })
    g["is_extrapolated_tail"] = False
    rows.append(pd.concat([g, tail], ignore_index=True))
hazard_ext = pd.concat(rows, ignore_index=True)

# ---------------------------------------------------------------------------
# 2. Survival curve and TTF per model group
# ---------------------------------------------------------------------------
def survival_and_ttf(g):
    g = g.sort_values("bin_start_days").reset_index(drop=True)
    surv_end_of_bin = np.cumprod(1 - g["hazard_30d"].values)  # S at the END of each bin
    g["survival_S"] = surv_end_of_bin
    n = len(g)
    expected_ttf = np.zeros(n)
    median_ttf = np.zeros(n)
    median_ttf_is_beyond_tail = np.zeros(n, dtype=bool)
    for i in range(n):
        s_at_i = surv_end_of_bin[i - 1] if i > 0 else 1.0  # survival at the *start* of bin i
        cond_surv = surv_end_of_bin[i:] / s_at_i            # S(t | survived to start of bin i)
        # expected residual life = area under conditional survival curve (trapezoid, bin_days wide)
        expected_ttf[i] = np.trapezoid(np.concatenate([[1.0], cond_surv]), dx=BIN_DAYS)
        below_half = np.where(cond_surv <= 0.5)[0]
        if len(below_half) > 0:
            median_ttf[i] = (below_half[0] + 1) * BIN_DAYS
        else:
            median_ttf[i] = np.nan
            median_ttf_is_beyond_tail[i] = True
    g["expected_ttf_days"] = expected_ttf
    g["median_ttf_days"] = median_ttf
    g["median_ttf_beyond_tail"] = median_ttf_is_beyond_tail
    return g

ttf_parts = []
for grp, g in hazard_ext.groupby("model_grp"):
    g = survival_and_ttf(g.copy())
    g["model_grp"] = grp
    ttf_parts.append(g)
ttf = pd.concat(ttf_parts, ignore_index=True)
# Only keep the observed (non-tail) rows in the published lookup table -- the
# tail exists purely to make the integral/median well-defined, it isn't a
# real prediction surface a caller should look up directly.
ttf_observed = ttf[~ttf["is_extrapolated_tail"]].drop(columns=["is_extrapolated_tail"])
ttf_observed.to_csv(PROCESSED / "ttf_lookup_table.csv", index=False)
print(f"Saved -> data/processed/ttf_lookup_table.csv ({len(ttf_observed):,} rows)")

frac_beyond = ttf_observed["median_ttf_beyond_tail"].mean()
print(f"Rows where median residual life exceeds the {TAIL_EXTRA_BINS * BIN_DAYS / 365:.0f}-year "
      f"constant-hazard tail (i.e. 'more reliable than we can estimate'): {frac_beyond:.2%}")

# ---------------------------------------------------------------------------
# 3. Face-validity check: predicted TTF at age 0 vs. what actually happened
#    to real drives of each model group
# ---------------------------------------------------------------------------
drv = pd.read_csv(PROCESSED / "backblaze_drives_clean.csv").dropna(subset=["age_days"])
top_models = ttf_observed.loc[ttf_observed["model_grp"] != "OTHER", "model_grp"].unique()
drv["model_grp"] = np.where(drv["model"].isin(top_models), drv["model"], "OTHER")

actual_by_group = drv.groupby("model_grp").agg(
    n_drives=("failed", "size"),
    failure_rate=("failed", "mean"),
    median_age_days=("age_days", "median"),
    median_age_at_failure=("age_days", lambda s: s[drv.loc[s.index, "failed"] == 1].median()),
)
predicted_at_0 = ttf_observed[ttf_observed["bin_start_days"] == 0][
    ["model_grp", "expected_ttf_days", "median_ttf_days", "median_ttf_beyond_tail"]
].set_index("model_grp")

face_validity = actual_by_group.join(predicted_at_0).sort_values("failure_rate", ascending=False)
fv_display = face_validity.copy()
fv_display["failure_rate"] = fv_display["failure_rate"].map(lambda x: f"{x:.2%}")
for col in ["median_age_days", "median_age_at_failure", "expected_ttf_days", "median_ttf_days"]:
    fv_display[col] = fv_display[col].map(lambda x: "n/a" if pd.isna(x) else f"{x:,.0f}")
print("\nFace validity -- predicted TTF (from age 0) vs. real outcomes, by model group:\n")
print(fv_display.to_string())

# ---------------------------------------------------------------------------
# 4. Concordance index (C-index): does a lower predicted TTF actually
#    correspond to failing sooner, across real drives? Standard survival-
#    model evaluation metric. Exact computation is O(n^2) over 122k drives,
#    so this Monte-Carlo-samples comparable pairs -- a standard practical
#    approximation for a dataset this size.
# ---------------------------------------------------------------------------
rng = np.random.default_rng(42)
risk = drv.merge(predicted_at_0, on="model_grp", how="left")
risk["risk_score"] = -risk["expected_ttf_days"]  # higher risk = shorter predicted life

N_PAIRS = 300_000
idx_a = rng.integers(0, len(risk), N_PAIRS)
idx_b = rng.integers(0, len(risk), N_PAIRS)
a, b = risk.iloc[idx_a].reset_index(drop=True), risk.iloc[idx_b].reset_index(drop=True)

# Pair (a,b) is "comparable" under the standard survival convention when we
# can be sure who failed first: a failed and a's age <= b's observed age
# (b was still at risk at least that long, whether b failed later or was censored).
comparable = (a["failed"] == 1) & (a["age_days"] <= b["age_days"]) & ~(
    (a["age_days"] == b["age_days"]) & (a["failed"] == b["failed"])
)
concordant = comparable & (a["risk_score"] > b["risk_score"])
tied_risk = comparable & (a["risk_score"] == b["risk_score"])
c_index = (concordant.sum() + 0.5 * tied_risk.sum()) / comparable.sum()
print(f"\nConcordance index (TTF ranking vs. real outcomes, {comparable.sum():,} comparable "
      f"sampled pairs): {c_index:.4f}  (0.5 = random, 1.0 = perfect ranking)")

print("\nDone.")
