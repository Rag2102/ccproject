# Elkan, The Foundations of Cost-Sensitive Learning (IJCAI 2001)

Source read: the full 6-page PDF from the author's page.

| Field | Notes |
| --- | --- |
| Problem | Optimal decisions when different errors cost different amounts, and how to get a classifier to make them. |
| Data | None; theory plus short arguments about Bayesian and decision-tree learners. |
| Baseline | Standard accuracy-maximising classifiers and rebalancing of training sets. |
| Metric | Expected cost under a cost matrix. |
| Claim | The optimal two-class decision uses the threshold p* = (c10 - c00) / (c10 - c00 + c01 - c11) (equation 2), so a 2x2 cost matrix has one degree of freedom for decisions. Rebalancing training data has little effect on standard learners; learn from the data as given, then apply the threshold to calibrated probabilities (section 5). |
| Limitation | Example-dependent costs are called "only just beginning"; no budget constraint is treated. |
| What we reuse | The decision rule, the warning that costs must share one baseline (section 1.2), and the advice not to rebalance. |
| Reviewer would say | "Expected-cost thresholding is textbook. What is new?" (This is the attack of mock-review persona R3, the skeptic, in the v2 appendix.) |

## Consequences for this project

- v1's rule, migrate when p x failure cost x urgency > migration cost, reduces to Elkan's threshold with example-dependent costs when urgency is 1: p > c_migrate / c_fail for each VM. A fixed threshold is optimal only when the cost ratio is constant across VMs; v1's gain at rho > 0.3 is the gain from letting the threshold vary with the VM.
- The novelty therefore cannot be "expected-cost thresholding". It has to be (a) a budget-constrained policy (BAM: rank by benefit per unit of the budgeted resource), (b) where it beats a tuned threshold and where it does not, as a surface over correlation, spread and estimation error, measured on real placement, and (c) the open benchmark.
- v1's decision to retrain the hazard model without class balancing (Task 3) agrees with section 5. v1's Task 5 check (failure cost 600x migration cost) fails section 1.2's baseline test: both sides carry the same criticality weight, so it cannot show anything.
