# Kaplan-Meier Baseline: An Independent Check on the Hazard Model

## Why this exists

Task 3's HistGBM hazard model was validated against held-out person-period rows (ROC-AUC 0.781, tight calibration deciles) -- a real validation, but one that never directly asks whether the model's *implied survival curve* tracks the classical, model-free Kaplan-Meier estimator computed straight from the raw failure/censoring data. This closes that gap with the standard non-parametric estimator used throughout reliability engineering and biostatistics.

`scikit-survival`/`lifelines` are not installable in this project's sandboxed dev environment (the same constraint documented in `docs/task11_summary.md`), so the estimator is hand-computed from its closed-form definition -- short enough that this is not a real limitation:

**S(t) = product over all failure times t_i <= t of (1 - d_i / n_i)**, where n_i is the number of drives still at risk immediately before t_i and d_i is the number of real failures exactly at t_i. Censored drives (still healthy when observation ended) leave the risk set at their own observed age without counting as a failure -- the standard right-censoring rule.

## Result

| group                           |   n_drives |   n_failures |   max_abs_survival_diff |   mean_abs_survival_diff |
|:--------------------------------|-----------:|-------------:|------------------------:|-------------------------:|
| Fleet-wide (all drives)         |     122618 |         6912 |                  0.051  |                   0.022  |
| ST3000DM001 (flagged bad batch) |       4707 |         1708 |                  0.0482 |                   0.0153 |
| ST12000NM0007 (most reliable)   |       7242 |           17 |                  0.0012 |                   0.0007 |

Note on the fleet-wide panel: the model-free Kaplan-Meier curve there pools ALL drives regardless of model; the HistGBM overlay necessarily has to pick one model_grp to condition on (predict_proba requires a value for that categorical feature), so it uses the single highest-count group (ST4000DM000) as a representative rather than a true model-agnostic average -- stated plainly so the fleet-wide panel is read as an illustrative comparison, not an apples-to-apples one. The two per-model panels (ST3000DM001, ST12000NM0007) are genuinely apples-to-apples: both curves condition on the same real model group.

## Interpretation

The two per-model comparisons (ST3000DM001, the publicly-flagged bad Seagate batch, and ST12000NM0007, the fleet's most reliable model) are the ones that matter, since they condition the HistGBM curve on the correct real model group. Both show the parametric model tracking the non-parametric ground truth closely across the observed age range -- the maximum survival-probability gap between the two curves stays small in both cases, and critically, the HistGBM curve does not systematically drift in one direction (over- or under-estimating survival) as age increases. This is exactly what a well-calibrated model should look like next to its model-free counterpart, and it is a genuinely independent check: the person-period ROC-AUC/Brier metrics and this survival-curve comparison could in principle have disagreed (a model can rank well and calibrate well in aggregate while still tracking the wrong curve shape), and they don't.

See `docs/figures/kaplan_meier_vs_histgbm.png` for the plotted curves and `data/processed/kaplan_meier_comparison.csv` for the numbers.

## Output

- `data/processed/kaplan_meier_comparison.csv`
- `docs/figures/kaplan_meier_vs_histgbm.png`
- `scripts/09_kaplan_meier_baseline.py` -- rerunnable end to end (~10s)
