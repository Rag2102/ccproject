# ADR-011: confirm the avoidance finding on fresh seeds
Status: **accepted** (owner asked for this confirmation, 1 Nov 2026; rule written before any run on these seeds)
Date: 2026-11-01

Context. ADR-010 found, as exploratory, that marking the riskiest hosts so they take no new VMs (P0+avoid) saves more than BAM and P5 against never migrating. That finding has been read on eval seeds 1-30, so those seeds cannot confirm it. It also used the oracle predictor, the upper bound.

Decision. A separate test on seeds no result has used. It does not touch the 30-comparison family, the G3 rule or `PROTOCOL.md` v1.0.

## Primary test (6 comparisons)

- Seeds: 2001-2050 (n = 50). Regimes: B1, B2 (trace-calibrated). Budget: 2%. Predictor: oracle, as the main matrix. Marking share: 2%, as ADR-010.
- Measure: S = (C_P0 - C) / C_P0 per seed, the saving against never migrating.
- Comparisons, in each of B1 and B2: P0+avoid against P0, P4 and P5, as paired per-seed differences in S.
- Pass for one comparison: mean difference ≥ 1 point, Holm-adjusted two-sided Wilcoxon p < 0.05 (Holm over these 6) and the 95% BCa interval above zero.
- **Confirmed** if all 6 pass. **Partly confirmed** if P0+avoid beats P0 in both regimes and at least one other comparison passes; say which. **Not confirmed** otherwise. The label follows this rule, and all 6 are reported in any case.

## Secondary (reported, not part of the verdict)

- Rejected arrivals per run for P0 and P0+avoid, with no threshold.
- P4+avoid at 2% against P0+avoid: what migration adds.
- Imperfect predictors: P0+avoid and P4 with logit noise σ ∈ {0.5, 1, 2}, and the shuffled-score control, which should remove avoidance's benefit.

## Limits

Simulation only. Confirmation covers these regimes and this marking share. Seeds test chance, not simulator misspecification. The result is post-freeze and stays labelled as such in the paper.

Implementation: `scripts/v2/50_confirm_avoid.py`; rows in `results/explore/avoid_confirm/`, summary in `results/summary/avoid_confirm.json`.
