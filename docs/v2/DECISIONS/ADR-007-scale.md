# ADR-007: scale of the evaluation runs (hosts, horizon, eval seeds)
Status: **proposed**. The decision is the owner's, at the Week 17 freeze.
Date: 2026-10-04

Context: `PROTOCOL.md` section 6. The pilot (seeds 201-205; cells A3 and B1 at a 2% budget; 2,000 hosts × 365 days + 30 warm-up) measures SD(Delta) of P3 vs P2 as a proxy. n, hosts and horizon are chosen so that this SD is below the Bonferroni column (30 seeds: 1.6%; 50: 2.1%; 100: 3.1%). delta = 1% never moves. Under ADR-005, P2 is the budget-tuned threshold.

Evidence (`results/v2/pilot_w14b.json`; arrival blend calibrated, so A3 achieves 0.250 against the 0.256 target under P0):

| Cell | SD(Delta), P3 vs P2 | 95% upper bound of the SD (4 df) | Bonferroni bound, n = 30 |
| --- | --- | --- | --- |
| A3 | 0.67% | 1.59% | 1.6% |
| B1 | 1.22% | 2.89% | 1.6% |

For comparison, the first pilot (uncalibrated A3) gave 1.0% at A3 against budget-tuned P2. Run time is 3-9 s per (policy, seed) at 2,000 hosts on one core, with 10 processes sharing the machine.

**Recommendation:** 2,000 hosts, 365 days + 30 warm-up, n = 30 eval seeds (1-30), with a pre-specified extension:
- If, after the run, the observed SD(Delta) of any confirmatory comparison exceeds 1.6%, that cell's regime is extended to n = 50 (seeds 31-50) for every policy.
- The decision then uses n = 50 and its Bonferroni bound of 2.1%.
- The extension depends only on the SD, never on the sign or size of Delta.

Why:
- The point estimates meet the rule at n = 30, with a margin of 2.4× (A3) and 1.3× (B1).
- A 5-seed SD is imprecise: B1's upper bound is above 1.6%. The extension covers that case without paying for it in advance.
- 2,000 hosts keeps the main matrix (10 cells × 4 budgets × about 10 policies × 30 seeds) at an estimated 6-8 hours on 8 cores. P2 tuning (40 cell-budget pairs on dev seeds) adds about 2 hours.

Alternatives:
- 5,000 hosts × 365 days, n = 30. SD falls by about √2.5, so B1's upper bound is about 1.8%. Compute is about 2.5× larger (roughly a day for the main matrix).
- 2,000 hosts, n = 50 from the start (bound 2.1%). Compute is about 1.7×.
- 180 days. Not considered: the drift study and regime D need a year.

Consequences: SIM_SPEC section 11 ("hosts per cluster 2,000-5,000, set by the pilot") becomes 2,000. Replication seeds are 1001-1030, extended to 1050 under the same rule.
