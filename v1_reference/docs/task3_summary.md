# Task 3 — Failure Probability Model: Results

## Why not a plain classifier

The Backblaze table has one row per drive: its final age and whether that final event was a real failure or a censoring (still healthy when observation ended). Training `failed ~ model + age` directly on that table would leak the future — a drive's *final* age is only knowable once its outcome is already known. This is a textbook survival-analysis setup, so the data was expanded into **person-period** rows: one row per 30-day interval each drive is known to have survived through, labeled 1 only on the interval containing its failure. A classifier trained on that table learns h(t) = P(fail in this 30-day interval | survived to the start of it) — a proper discrete-time hazard model, using only information available at the start of each interval. Chaining h(t) forward gives P(failure within any lookahead window), which is the actual input the mitigation policy (task 6) needs.

- 122,618 drives → 3,462,344 person-period rows, 0.1996% positive rate per 30-day interval (consistent with the ~5.6% lifetime failure rate spread across a median ~750-day lifespan).
- Split at the **drive** level (`GroupShuffleSplit`, 80/20) so no drive's intervals leak across train/test.
- Features: drive-model group (top 15 models + "OTHER"), capacity (TB), and interval start age — this directly encodes the task 2 finding that drive model dominates age as a failure signal.

## Two candidates, and a calibration fix

Logistic regression (interpretable hazard baseline) and `HistGradientBoostingClassifier` (handles the non-monotonic age-hazard shape from task 2 without manual feature engineering) were both trained.

**First pass used `class_weight="balanced"`, which was wrong and got corrected before finalizing.** Balancing inflates the minority-class probability scale — it can still rank drives fine (ROC-AUC looked identical), but the actual probability *values* come out badly miscalibrated (e.g., predicting ~0.5–0.7 for drives that truly fail at a ~0.002–0.009 rate). Since the mitigation policy in task 6 multiplies this probability directly into an expected-cost formula, using the miscalibrated version would have silently corrupted every downstream decision even though the model "looked" fine on ROC-AUC alone. Retrained without balancing:

| Model | ROC-AUC | PR-AUC | Brier |
|---|---|---|---|
| Logistic hazard | 0.753 | 0.017 | 0.00203 |
| **HistGBM hazard (selected)** | **0.781** | **0.020** | **0.00202** |

PR-AUC of ~0.02 against a ~0.002 base rate is roughly a 10x lift over random — modest in absolute terms but in line with what published SMART-based failure-prediction work generally reports; rare hardware failures with a 30-day lead time are a genuinely hard prediction problem, not a bug in this pipeline.

**Calibration (the part that actually matters for task 6)** — predicted-risk decile vs. real outcome rate, now tight across the board:

| predicted risk decile (mean) | empirical failure rate |
|---|---|
| 0.00014 | 0.00021 |
| 0.00049 | 0.00039 |
| 0.00096 | 0.00094 |
| 0.00199 | 0.00218 |
| 0.00906 | 0.00944 |

(full 10-decile table in the script output). Predicted and actual track closely at every risk level — this is the property the cost-sensitive policy actually depends on.

## What was produced

- **`models/failure_probability_model.joblib`** — the trained HistGBM hazard model.
- **`data/processed/hazard_lookup_table.csv`** (1,584 rows = 16 model groups × 99 thirty-day age bins) — precomputed `hazard_30d` and `p_fail_within_window` (30-day lookahead) per (model group, age). This is what the replay simulator (task 8) will actually query — a plain CSV lookup, no sklearn needed at simulation time.
- `scripts/02_failure_probability_model.py` — rerunnable end to end (~30s).

## Feeds into next

Task 4 (time-to-failure) reuses this same hazard model rather than rebuilding one: TTF is derived from the survival curve S(t) = Π(1 − h(k)) that's already implicit in the hazard lookup table (expected/median remaining life), so that step is mostly composition, not new modeling.
