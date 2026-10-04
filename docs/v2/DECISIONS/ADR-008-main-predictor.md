# ADR-008: the main matrix uses the oracle on the validated hazards; model-based worlds are a robustness run
Status: accepted (owner, 4 Oct 2026)
Date: 2026-10-04

Context: SIM_SPEC section 7 describes drives replayed from Backblaze with daily scores from the v2 model. As built and validated at G2, drive hazards come from v1's lookup (model group and age, `failure.drive_hazard_v1`) plus a Weibull non-disk term, and the oracle predictor gives each host its true conditional probability (A1 holds by construction). ADR-006 chose the 20-model ensemble. Replaying it needs:
- full daily features (the stored features are a ~2% sample of drive-days: about 670k rows per quarter for 300k drives);
- scoring about 330 million drive-days with 20 models;
- drive replay in the engine.

That is about a day of work and compute.

Decision: the confirmatory matrix (A1-A7, E1-E3, B1, B2, C, D) uses the validated hazards and the oracle predictor, with the noisy, miscal, drift and noise predictors where the protocol names them. Model-based worlds (drive hazards and scores from the ensemble) are a **pre-registered robustness run in Week 20**, on B1, B2 and C at 1% and 2%, labelled exploratory. They are not part of the 30-comparison family.

Alternatives considered:
- Build model replay first. Rejected by the owner: delays Week 18 by about a day.
- Add the model-replay variants to the confirmatory family. Rejected: more comparisons for Holm, and the variants would be specified before they exist.

Consequences:
- The spread of host risk in the main matrix is that of v1's lookup hazards. The ensemble ranks drives much more sharply (test ROC-AUC 0.90 against 0.63 for v1's features), so the main matrix probably understates how far p is spread across hosts (σ_x in THEORY.md T3).
- The paper states this as a limitation, and the Week 20 run measures its size.
- SIM_SPEC section 9's `model` predictor stays specified and unbuilt until Week 20.
