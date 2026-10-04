# Tasks for Weeks 7-9 (16 Nov - 6 Dec 2026)

Taken from the v5 week cards for W7, W8 and W9 (plan pages 17-18). Started 4 Oct 2026, ahead of the calendar, while the Backblaze ingest was still running. `[x]` = done and checked; `[~]` = done, needs you; `[ ]` = not done.

## Week 7 (16-22 Nov): temporal hazard model v2

About 12 h.

- [x] Features: `scripts/v2/11_features.py`.
  - log1p of SMART 5, 187, 188, 197 and 198, with 7- and 30-day deltas and 30-day maxima;
  - age as the 30-day running maximum of power-on hours;
  - temperature and its 30-day maximum;
  - days since SMART 5 and 197 first became non-zero;
  - model, capacity, and missing flags.

  Every window is trailing.
- [x] Labels for H = 7, 14 and 30 with the Week 5 censoring rule. Drive-days far from a failure are sampled at 2%, with inverse-probability weights; the weights check out against the full counts (within 0.03% on 2018 Q2).
- [x] Splits: 70/15/15 by calendar time over the last three years. A point whose label is not decided inside its split is dropped, and drives that fail in the test period are excluded from training. Rolling origin with three 3-month folds.
- [x] Models (`scripts/v2/12_train.py`):
  - HistGradientBoosting;
  - logistic regression as a sanity check;
  - **v1's features refitted on the same temporal data** (model group, capacity, age). v1's own model was trained on a random split, so refitting isolates the effect of the features.
  - LightGBM was not installable (needs the system library `libomp`), which the plan allows.
- [x] Isotonic calibration on the validation period; reliability diagram; ECE (20 equal-count bins).
- [x] Test-period metrics: ROC-AUC, PR-AUC, Brier, ECE, precision in the top 1% and 5%. 95% CIs come from 1,000 Poisson bootstrap replicates over drives, plus a paired PR-AUC difference against v1. The fast metric code is checked against scikit-learn on every run.
- [x] Leakage audit, programmatic: no training row from a drive that fails in the test period; no training label that looks past the end of training; trailing windows by construction.
- [ ] Final run on 2023-2026 data (waits for the ingest), then `docs/v2/failure_model_v2.md`

## Week 8 (23-29 Nov): empirical rho; Gate G1

About 12 h.

- [x] Cells a, b and h, chosen before any data was read. Tirmazi et al. name them as the cells with the most production, best-effort batch and mid-tier work respectively. 51.8 GB of `instance_events` in all, downloaded one cell at a time from the public buckets (MD5-checked) and deleted after aggregation.
- [x] Pilot on cell a's machine table and first shard:
  - event codes confirmed (ADD at time 0 for 9,526 of 10,001 machines; dedicated machines are −1);
  - 5 platforms;
  - about 1.8 removals per machine per month, mostly maintenance, as expected.
- [x] `scripts/v2/13_trace_rho.py`:
  - placements → counts per (window, machine, tier, scheduling class);
  - three risk proxies;
  - τ-b and tie-corrected Spearman from contingency tables (checked against SciPy);
  - 2,000-resample machine bootstrap (BCa);
  - Gini dispersion;
  - mapping to the latent axis;
  - G1 class per cell and majority.
- [x] Axis made precise before any estimate: pH = 0.30 is v1's tie-corrected Spearman under v1's margins, which is **0.375** on the latent axis (`rho_definition.md` step 6, `PROTOCOL.md` v0.2). Confirmed 4 Oct.
- [ ] Run cells a, b and h, then `--analyse`; figure F3 draft (`v2_trace_rho.pdf`)
- [ ] Mapping sensitivity (M2, M3) is in the table; if the sign changes, it goes in the first paragraph
- [~] `docs/v2/G1_decision.md`: drafted from the result, **signed off by you**. The class is final under the protocol.

## Week 9 (30 Nov-6 Dec): citable v1 report

- [x] Decision: **skipped** (4 Oct). No application needs it before the v2 paper; the hours move to Week 10. Logged in `LOG.md` with the caveat that a revived report needs a correction for the -3.1% result.

## Week 10 (7-13 Dec): simulator v2 design spec (started 4 Oct, using Week 9's hours)

- [x] `docs/v2/SIM_SPEC.md` v0:
  - entities and fields;
  - time model and event tie order;
  - six event types plus HOST_REPAIR, with state transitions;
  - accounting with units, charging realised costs only, so v1's asymmetry cannot recur;
  - migration model with v1's closed form for the regression;
  - failure process and the common-random-numbers contract;
  - placement per regime, predictor and policy interfaces;
  - parameter table with sources;
  - 9 invariants, architecture, performance target (≤ 10 s per policy-seed at 5,000 hosts × 365 days), G2 validation.
- [x] Three open items confirmed with their defaults (4 Oct): survival-weighted interruption cost, 70% initial fill, repaired host returns empty
- [ ] Reader test: someone reads it for 30 minutes and lists their questions
