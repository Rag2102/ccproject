# ADR-006: the simulator's failure model is chosen on validation PR-AUC
Status: accepted (owner, 4 Oct 2026). Rule written and committed before the validation scores were computed. The result is appended below.
Date: 2026-10-04

Context: `TrainedModel` (the simulator's model-based predictor) needs one Week 7-style model at H = 30. There are three candidates, all on Week 7's split (train 2023-07-01..2025-08-05, validation 2025-08-06..2026-01-16, test 2026-01-17..2026-06-30, v2 features):
- **boosted**: the single gradient-boosting model of Week 7 (`data/v2/models/v2_h30.joblib`);
- **logit**: logistic regression on the same features (`logit_h30.joblib`);
- **ensemble**: the mean of the 20 bootstrap-trained boosted models of Week 16 (`scripts/v2/21_uncertainty_drift.py`, seed 16).

Their **test** PR-AUC is already known: 0.074, 0.091 and 0.131 after isotonic calibration. Choosing on those numbers would make the test period part of the model choice. The choice is therefore made on the validation period. This is not blind, since the test results have been seen, but the rule below is fixed before any validation score exists.

Decision (the rule):
1. **Score.** Drive-day-weighted PR-AUC (`12_train.metrics`) on the validation period at H = 30, computed on **raw** scores (before isotonic calibration), because the isotonic maps are fitted on this same period. The ensemble's raw score is the mean of its members' raw probabilities. Boosted and logit are the saved Week 7 models. The ensemble's members were not saved, so they are refitted exactly as in Week 16 (same data, features, hyperparameters and bootstrap seed).
2. **Winner.** The highest validation PR-AUC. If the 95% interval of the difference between the top two contains 0 (Poisson bootstrap over drives, 1,000 replicates, as in Week 7), take the simpler of the two. The order of simplicity is logit, then boosted, then ensemble.
3. **Afterwards.** The winner is calibrated isotonically on the validation period, as in Week 7. Its test-period numbers are reported, not used.
4. Whatever the result, the losing candidates appear in the paper's model table. The choice is not revisited after the policy results are seen.

Script: `scripts/v2/22_model_choice.py` → `results/v2/model_choice.json`.

Consequences: `TrainedModel` and the failure worlds for evaluation seeds 1-30 wait only for this result. The risk-averse BAM variant (Week 16) uses the ensemble's interval if the ensemble wins, and otherwise a bootstrap of the winner.

## Result
(appended after the run)
