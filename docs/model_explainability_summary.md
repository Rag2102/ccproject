# Model Explainability: Permutation Importance + Partial Dependence

## Why this exists

Task 3 established the HistGBM hazard model is accurate (ROC-AUC 0.781) and calibrated, and task 2's raw-data analysis found drive model dominates age as a failure signal. This closes the loop with a formal, quantified answer straight from the trained model itself: which of its three inputs actually drives a prediction, and by how much. `shap` is not installable in this project's sandboxed dev environment (same constraint as `scikit-survival`), so this uses scikit-learn's own built-in tools -- permutation importance (Breiman 2001) and partial dependence -- which need no extra package and answer the same top-level question.

## Method

Permutation importance was computed on a 50,000-row subsample of task 3's exact held-out test fold (reproduced via the identical `GroupShuffleSplit(random_state=42)`), scored on PR-AUC (chosen over ROC-AUC because the ~0.2%-positive-rate class imbalance makes PR-AUC the more sensitive metric for a rare-event problem) with 10 shuffles per feature.

## Result

| feature        |   mean_importance |   std_importance |
|:---------------|------------------:|-----------------:|
| model_grp      |       0.0225219   |      0.000334234 |
| bin_start_days |       0.0198296   |      0.000659427 |
| capacity_tb    |       0.000836488 |      0.00169736  |

**model_grp** (0.0225) and **bin_start_days** (0.0198) are close to each other and both far ahead of **capacity_tb** (0.0008, close to zero) -- corroborating task 2's raw-data finding (drive model dominates age as a failure signal) directly from the trained model's own behavior rather than from the input data alone, and adding a new finding beyond what task 2 established: capacity_tb carries almost no independent predictive signal once model_grp is known. This makes sense structurally -- capacity is largely a proxy for drive model (most models ship at one or two fixed capacities), so once the model itself is in the feature set, capacity has little new information left to contribute. This is a genuine, useful finding for anyone extending the model: a future feature-engineering pass could likely drop capacity_tb with negligible accuracy loss, simplifying the model without a real cost.

See `docs/figures/model_explainability.png` for the three panels: permutation importance, the partial dependence curve for age, and mean predicted hazard by drive model (the categorical analogue of a partial dependence plot, since PDP's uniform-grid-averaging approach isn't a natural fit for an unordered category). The third panel visibly reproduces the same real-world artifact task 4 found from the survival curve directly -- ST3000DM001 (the publicly-flagged bad Seagate batch) has by far the highest mean predicted hazard of any group, now confirmed through a completely different lens (average model output) rather than derived TTF.

One honest note on the age partial-dependence curve: it gets visibly noisy past ~2,200 days, swinging sharply before settling again. This lines up with task 4's own documented caveat that hazard estimates near the edge of the observed data (Backblaze drives are tracked out to ~8 years, and very few survive that long) are thin-sample and should not be over-read -- the same limitation, now visible directly in the model's partial dependence rather than only in the TTF write-up.

## Output

- `data/processed/permutation_importance.csv`
- `docs/figures/model_explainability.png`
- `scripts/10_model_explainability.py` -- rerunnable end to end (~1-2 min, dominated by the person-period rebuild)
