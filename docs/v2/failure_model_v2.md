# Failure model v2

Week 7 (card 16-22 Nov; run 4 Oct 2026). Code: `scripts/v2/11_features.py`, `scripts/v2/12_train.py`. Label rules: `label_spec.md`. Numbers: `results/v2/model_v2_metrics.csv`, `results/v2/model_v2.json`; reliability diagram `results/figures/v2_reliability.pdf`. The table between the "generated" markers is rewritten by the training script; everything else is written by hand.

## Data and split

- Drive-days from the last three years (2023-07-01 to 2026-06-30), 2% of those far from a failure kept with weight 50 and every day within 30 days of a failure kept (`label_spec.md`).
- Split by calendar time: train to 2025-08-05, validation to 2026-01-16, test from 2026-01-17 to 2026-06-30.
- Test set: 983,756 sampled points, 328,041 drives, 55,606 positive at H = 30 (the base rate after reweighting is 0.12% of drive-days).
- Leakage audit, all three horizons: no training row from a drive that fails in the test period; no training label that looks past the end of training; every feature window is trailing.

## Results

1. **The SMART features carry the signal.** At H = 30, v1's features refitted on the same data (model group, capacity, age) reach PR-AUC 0.0018, barely above the base rate of 0.0012, and ROC-AUC 0.63. The v2 features reach 0.074 and 0.88. The paired difference in PR-AUC is 0.065 to 0.082 (95% bootstrap over drives). The same holds at H = 14 and 7. v1's model was trained on a random split of drives, so its reported accuracy did not measure prediction forward in time; refitted forward in time, its features are close to uninformative at the drive-day level.
2. **The model class matters less than the features.** Logistic regression on the same features has a *higher* PR-AUC than gradient boosting (0.091 [0.082, 0.105] against 0.074 [0.067, 0.084]; the intervals barely overlap) and a slightly lower ROC-AUC (0.876 against 0.884). The two differ at the very top of the ranking, which is where PR-AUC is decided. Precision in the top 1% is the same (5.4% and 5.6%, about 46 times the base rate).
3. **Calibration.** Isotonic calibration on the validation period brings ECE to 2.3 × 10⁻⁴ and halves the Brier score of the raw boosted model (2.2 × 10⁻³ to 1.1 × 10⁻³).
4. **Stability over time.** Rolling origin, 3-month test folds: PR-AUC 0.114, 0.115 and 0.044 (ROC-AUC 0.876, 0.870, 0.849). The last fold (Oct 2025 to Jan 2026) is much weaker. Whether that is a change in the fleet, a few models dominating failures, or noise is not yet known. Week 12's predictor inherits it, and Week 20's noisy-predictor sweep covers the range.

## Decision needed: which model the simulator uses

The plan names gradient boosting as the v2 model, but the logistic regression ranks the top better on the test period. Choosing on the test period would be selection on the test set. **Proposal:** pick by PR-AUC on the validation period, record the rule in `PROTOCOL.md` before looking, and keep the other model as a sensitivity run. Both are saved (`data/v2/models/v2_h*.joblib`, `logit_h30.joblib`).

## Limitations

- These are drive models. A host's probability is composed from its drives and an assumed non-disk term in the simulator (`SIM_SPEC.md` section 7).
- PR-AUC and precision are computed with the sampling weights; the 2% sample adds variance to the negatives, which the drive bootstrap includes.
- Precision in the top 1% of drive-days is 5.6%: most flagged drives do not fail within 30 days. This is why migration cost and budget matter, which is the question of the paper.

<!-- generated: metrics table -->
| H | model | ROC-AUC | PR-AUC | Brier | ECE | precision, top 1% | precision, top 5% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | v2 | 0.8844 [0.8754, 0.8937] | 0.0743 [0.0669, 0.0837] | 1.14e-03 [1.09e-03, 1.18e-03] | 2.32e-04 [1.96e-04, 2.92e-04] | 0.0556 [0.0526, 0.0588] | 0.0170 [0.0161, 0.0178] |
| 30 | logit | 0.8755 [0.8661, 0.8843] | 0.0913 [0.0818, 0.1048] | 1.13e-03 [1.08e-03, 1.18e-03] | 1.65e-04 [1.30e-04, 2.29e-04] | 0.0544 [0.0512, 0.0576] | 0.0159 [0.0151, 0.0167] |
| 30 | v1 | 0.6314 [0.6204, 0.6417] | 0.0018 [0.0017, 0.0019] | 1.20e-03 [1.14e-03, 1.24e-03] | 2.05e-04 [1.82e-04, 2.63e-04] | 0.0024 [0.0018, 0.0031] | 0.0020 [0.0018, 0.0021] |
| 14 | v2 | 0.8764 [0.8669, 0.8859] | 0.0485 [0.0438, 0.0541] | 4.93e-04 [4.74e-04, 5.14e-04] | 6.31e-05 [5.05e-05, 8.81e-05] | 0.0255 [0.0242, 0.0270] | 0.0071 [0.0067, 0.0074] |
| 14 | v1 | 0.6237 [0.6118, 0.6354] | 0.0008 [0.0007, 0.0008] | 5.09e-04 [4.89e-04, 5.31e-04] | 1.18e-04 [1.03e-04, 1.39e-04] | 0.0008 [0.0007, 0.0010] | 0.0009 [0.0008, 0.0010] |
| 7 | v2 | 0.8686 [0.8589, 0.8789] | 0.0317 [0.0281, 0.0360] | 2.39e-04 [2.29e-04, 2.50e-04] | 4.10e-05 [3.34e-05, 5.25e-05] | 0.0135 [0.0128, 0.0143] | 0.0033 [0.0032, 0.0035] |
| 7 | v1 | 0.6308 [0.6187, 0.6423] | 0.0004 [0.0003, 0.0004] | 2.44e-04 [2.34e-04, 2.55e-04] | 4.52e-05 [3.88e-05, 5.73e-05] | 0.0004 [0.0003, 0.0005] | 0.0004 [0.0004, 0.0005] |

Splits: {'train': ['2023-07-01', '2025-08-05'], 'val': ['2025-08-06', '2026-01-16'], 'test': ['2026-01-17', '2026-06-30']}
<!-- generated: metrics table -->
