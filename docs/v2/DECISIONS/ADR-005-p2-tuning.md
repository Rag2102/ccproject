# ADR-005: P2 is tuned to use the budget, as the protocol says
Status: accepted (owner, 4 Oct 2026)
Date: 2026-10-04

Context: `PROTOCOL.md` defines P2, the comparator for the win criterion, as a threshold policy "tuned to use the budget": on the dev seeds, the threshold and within-host order that bring budget utilisation to about 95%. The Week 14 pilot (2,000 hosts × 365 days, 2% budget) showed what that comparator costs. At A1, P2 costs 123,643 against 31,906 for never migrating (about 3.9×), because migration cost dominates under v1's cost constants and the rule forces the budget to be spent on low-risk VMs. A cost-tuned alternative (P2c: the threshold and order with the lowest cost on dev seeds) was proposed and run in the pilot. At A1 it never migrates (equal to P0); at A3 it is 2.4% below P0.

Decision: keep the protocol's rule. P2 is tuned to use the budget (`tune_p2(..., criterion="budget")`, target utilisation 0.95), per cell and budget, on dev seeds 101-110. P2c is not a comparator, primary or secondary. The pilot outputs that contain it (`results/v2/pilot_w14*.json`) stay as recorded.

Alternatives considered:
- Tune on cost (P2c) as the comparator. Rejected by the owner: it would change a pre-registered rule after seeing pilot results.
- Report both, with budget-tuned primary. Not chosen.

Consequences:
- The win criterion (`PROTOCOL.md`: mean Delta ≥ 1% and Holm-adjusted lower bound > 0) is measured against budget-tuned P2. Because P2 can cost more than never migrating, a win over P2 does not by itself show that a policy beats doing nothing. Every results table therefore shows P0 and P3 next to P2, so the reader can see that.
- P6's base policy is the budget-tuned P2. The Week 16 guard smoke (`scripts/v2/20_guard_smoke.py`) used the cost-tuned threshold and is rerun with the budget-tuned one.
- The scale decision uses the SD of Delta against P2, not P2c.
- Expected reviewer objection: "BAM wins against a straw man". The answer is the pre-registration, plus the P0 and P3 columns. It goes in the paper's threats section.
