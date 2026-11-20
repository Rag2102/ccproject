# ADR-006: the simulator's failure model is chosen on validation PR-AUC
Status: accepted (owner, 4 Oct 2026). Rule committed (0b05ff3) before the validation scores were computed; result appended below. **Winner: the ensemble.**
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
Run 4 Oct 2026, 21:59 (`scripts/v2/22_model_choice.py`, `results/v2/model_choice.json`, `logs/model_choice.log`). Validation period 2025-08-06..2026-01-16, 930,869 rows, H = 30, raw scores:

| Candidate | Validation PR-AUC [95% CI] |
| --- | --- |
| ensemble (20 bootstrap boosted models, mean) | 0.0939 [0.0827, 0.1100] |
| logit | 0.0720 [0.0621, 0.0845] |
| boosted (Week 7 single model) | 0.0704 [0.0614, 0.0819] |

The top two (ensemble vs logit) differ by 0.013 to 0.032 (paired bootstrap over drives). The interval excludes 0, so the tie rule does not apply. **The simulator uses the ensemble**, calibrated isotonically on the validation period. Its test numbers, reported and not used for the choice: PR-AUC 0.131, ROC-AUC 0.898 (`results/v2/uncertainty_w16.json`). The ensemble's 5-95% interval serves the risk-averse BAM variant.

On validation, unlike test, logit and boosted are indistinguishable (0.072 vs 0.070). Week 7's test-period lead of logit (0.091 vs 0.074) therefore did not carry over to validation.

**Deployed calibration (5 Oct 2026).** The ensemble exported for the web demo (`scripts/v2/25_export_ensemble.py`, `models/v2_ensemble/` on the site branch) follows step 3: one isotonic map fitted on validation to the mean of the 20 members' raw probabilities. Its validation PR-AUC on raw scores is 0.0939, which reproduces this rule's run exactly. Its test PR-AUC is **0.103** (ROC-AUC 0.894). Week 16's 0.131 came from a different calibration: each member calibrated separately, then averaged. That variant was not chosen here, and switching to it because it scores better on test would be selection on the test set. The model choice itself used raw scores and is unaffected. Wherever the deployed model is quoted, the number is 0.103.
