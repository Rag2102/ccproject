# v1 anomaly: why the threshold won at rho = 0 (Week 3)

Status: complete for Week 3 (4 Oct 2026). Eight verdicts: 1 confirmed, 5 rejected, 2 inconclusive. Numbers come from `scripts/v2/diag_v1_anomaly.py` (run time about 10 s), written to `results/summary/v1_anomaly.json` (result R13); figures are in `results/figures/v1_anomaly_*.pdf`.

## The answer in two sentences

The threshold won at rho = 0 because of how v1 counted, not because cost-awareness hurts. About 1 point of the -3.1% came from giving the threshold 8% more migrations (5,522 vs 5,116 hosts) and about 1 point from matching hosts rather than GB. The rest came from crediting a migration with averting any later failure (a median 170 days later, while the median VM lives 40 minutes), whereas the decision used a 30-day probability. With 30-day accounting at an exactly matched budget, the v1 rule is ahead of the threshold by 0.2% (0.4% on average over 10 other placements). That is inside the 1% materiality line, so at rho = 0 the two are equivalent.

| Comparison in the v1 world (rho = 0) | Delta, v1 rule vs threshold |
| --- | --- |
| v1 as published (threshold 5,522 hosts, v1 rule 5,116) | -3.1% |
| Same number of hosts (5,116 each) | -2.1% |
| Same GB of VM memory (452,291 GB each) | -1.1% |
| Same hosts, 30-day accounting | +0.2% |
| Same GB, 30-day accounting | +0.2% |

Delta = (C_threshold - C_policy) / C_threshold, positive when the v1 rule is better (the v5 definition). Figure: `results/figures/v1_anomaly_budgets.pdf`.

## 1. Reproduction from the tag

The number reproduces exactly. Re-running v1 from tag `v1.0-course` gives the same matched-budget comparison as the frozen results.

| Quantity | Re-run | v1_reference |
| --- | --- | --- |
| Cost, cost-sensitive (5,116 migrations) | 456,532.7 | 456,532.7 |
| Cost, threshold at matched budget (tau = 0.01468, 5,522 migrations) | 442,700.7 | 442,700.7 |
| Gap | cost-sensitive 3.1% higher | 3.1% |
| Missed failures, cost-sensitive vs matched threshold | 5,493 vs 5,311 | same |
| Cost, naive threshold (tau = 0.00731, 7,980 migrations) | 410,866.9 | 410,866.9 |

How it was checked:

- Worktree at the tag: `git worktree add ../ccproject-v1 v1.0-course`, then `python scripts/06_simulation_evaluation.py` from `scripts/`, with Python 3.12.14 and the pins in `v1_reference/pip_freeze_py312.txt`. Run time 11 s.
- `simulation_headline_summary.csv`: byte-identical to `v1_reference` (same SHA-256).
- `simulation_results_per_host.csv`: same shape (122,618 x 23) and columns; every outcome label identical; numeric columns differ by at most 8.9e-16, last-bit floating-point noise.
- The diagnostic script rebuilds the same world independently and asserts the three v1 costs to 0.01 before it runs anything else.

## 2. Method

In v1 a policy decides per host: all of a host's VMs move together, a migrated host is charged its migration cost M, and a host that fails without a migration is charged its failure cost F. Both policies use a score that rises with the host's 30-day failure probability p, so each is "a * p + b crosses a line":

| Policy | a | b |
| --- | --- | --- |
| Threshold (v1 baseline, P1 / P2) | 1 | 0 |
| v1 cost-sensitive rule (urgency is 1 everywhere, see H2) | F / M | 0 |
| BAM, count budget | F | -M |
| BAM, GB budget | F / GB | -M / GB |

One harness can then compare any two policies at an exactly matched budget: number of hosts or GB of VM memory, with ties broken by a fixed random order. Every comparison is repeated on 10 more VM placements (dev seeds 101-110) to show how much the result depends on v1's single seed.

Verdict rules were written into the script before its first run (`VERDICT_RULES`). Three tests were changed after that run, and one bug was fixed; section 4 lists each change and why.

## 3. Verdicts

| ID | Hypothesis | Verdict | Key number |
| --- | --- | --- | --- |
| H1 | Host-level p is miscalibrated after placement | Inconclusive | Observed / expected failures 1.03; one decile with abs(z) > 3; no difference by tier |
| H2 | Urgency(TTF) misbehaves | Rejected | Urgency is 1 in every row; the shortest expected TTF is 2,239 days |
| H3 | The budget is matched in count, not GB | Inconclusive (by 0.08 point) | -3.1% to -2.1% (exact count) to -1.1% (same GB) |
| H4 | The 58% Unknown class flattens costs | Rejected | At a fixed budget, reweighting Unknown moves Delta by at most 0.35 point |
| H5 | p is too noisy to rank by a product | Rejected | With calibrated p the v1 rule still loses by 1.8% under v1 accounting; noise shrinks the gap |
| H6 | Asymmetric accounting | **Confirmed** | Delta goes from -2.1% (any later failure counts) to +0.2% (30-day accounting) at the same budget |
| H7 | The density denominator is not the budgeted resource | Rejected | Host M and GB correlate at 0.999; changing the denominator moves Delta by at most 0.11 point |
| H8 | The baseline's within-host VM order | Rejected | The three orders change total cost by 0.014% (v1 moves whole hosts) |

### H1: host-level p miscalibrated after placement. Inconclusive

Over 3.46 million host-months, 6,912 failures were observed against 6,690 predicted (ratio 1.033). By decile of p, the top decile is under-predicted by 6% (3,126 observed vs 2,941 expected, z = 3.4) and the two lowest deciles are over-predicted (z = -2.2 and -2.4). By the host's majority tier the ratio is 1.05 (low) and 1.03 (medium), so random placement does not miscalibrate p by tier. One decile beyond abs(z) > 3 falls between the rejection rule (none) and the confirmation rule (two or more).

Caveats: this is in-sample (the hazard model was trained on 80% of these drives), and both policies see the same p, so miscalibration can only matter through the ratio F / M. The Week 7 temporal model, with intervals and an out-of-sample test period, closes this. Figure: `v1_anomaly_calibration.pdf`.

### H2: urgency(TTF) misbehaves. Rejected

`urgency = clip(30 / expected TTF, 1, 5)` exceeds 1 in none of the 1,584 lookup rows: the shortest expected TTF is 2,239 days. Urgency is identically 1, so the v1 rule is exactly "migrate when p * F > M", and the urgency term had no effect on any v1 number.

### H3: budget matched in count, not GB. Inconclusive by the rule; about two-thirds of the gap

v1's bisection could not match the count exactly, because many hosts share one hazard value. The threshold therefore received 5,522 hosts against the v1 rule's 5,116 (8% more) and 548,173 GB against 452,291 GB (21% more; its hosts averaged 99 GB against 88 GB). Matching exactly:

| Budget matching | Delta, v1 world | Mean over 10 dev placements (SD) |
| --- | --- | --- |
| v1 bisection (5,522 vs 5,116) | -3.12% | |
| Exact number of hosts | -2.11% | -2.10% (0.10) |
| Same GB | -1.08% | -0.98% (0.09) |

The pre-written rule required -1% or better in the v1 world; -1.08% misses it by 0.08 point, so the verdict is inconclusive. Substantively, the budget definition accounts for about 2 of the 3.1 points.

### H4: the Unknown class flattens costs. Rejected

The Azure trace labels 58% of VMs "Unkown" (sic), and v1 gives them the medium weight 0.6. Reweighting them changes the spread of F / M across hosts (SD of log F / M between 0.37 and 0.56), but at a fixed budget of 5,116 hosts it moves Delta by at most 0.35 point (from -2.11% to between -1.76% and -2.08%).

The pre-written test let the v1 rule's operating point move with the weight (4,010 hosts at weight 0.3, 6,216 at weight 1.0) and moved Delta by up to 2.7 points. That move is the budget level, not the cost spread (see deviations).

### H5: p too noisy to rank by a product. Rejected

In synthetic worlds (same hosts, VMs and observation ends; failures drawn from the model's own hazard, so p is calibrated by construction; 10 dev seeds; the same noisy p for both policies):

| Noise on log-odds of p (sigma) | 0 | 0.25 | 0.5 | 1.0 | 1.5 | 2.0 |
| --- | --- | --- | --- | --- | --- | --- |
| Delta, v1 accounting (any later failure) | -1.76% | -0.48% | -0.37% | -0.27% | +0.18% | +0.48% |
| Delta, 30-day accounting | +0.48% | +0.42% | +0.26% | +0.39% | +0.54% | +0.56% |

With perfectly calibrated p, the v1 rule still loses by 1.8% under v1's accounting. The loss is therefore not caused by noise, and added noise makes the gap smaller, not larger. Under 30-day accounting the v1 rule is ahead at every noise level, and on all 10 seeds at sigma = 0 (range +0.20% to +0.80%). That matches the theory target T2: no loss under calibrated p and a matched budget. Figure: `v1_anomaly_noise.pdf`.

### H6: asymmetric accounting. Confirmed (the main cause)

v1 charges a migration's cost now but credits it with averting the host's failure at any later time, while the decision uses the probability of failure in the next 30 days. Necessary migrations happened a median 170 days (v1 rule) and 182 days (threshold) before the failure, and 93% more than 30 days before. Over that time the migrated VMs are long gone: the median Azure VM in the trace lives 0.028 days (40 minutes), and 87.7% live less than a day. The accounting therefore pays for averting failures that would have hit other VMs months later.

| A migration averts a failure only within | 7 d | 30 d | 90 d | 365 d | any time (v1) |
| --- | --- | --- | --- | --- | --- |
| Delta, same number of hosts | +0.19% | +0.19% | +1.08% | -1.64% | -2.11% |
| Delta, same GB | +0.10% | +0.19% | +1.13% | -1.18% | -1.08% |

The sign flips between 90 and 365 days. Under the long-horizon accounting what matters is the probability of failure over a host's remaining life, for which p * F / M is the wrong scale. Under accounting that matches the decision horizon, the v1 rule is ahead. The 2x-budget runs show the same effect: BAM, which stops once the expected 30-day benefit turns negative, loses by 16% under v1 accounting and wins by 1.5-1.8% under 30-day accounting. Figure: `v1_anomaly_windows.pdf`.

### H7: density denominator is not the budgeted resource (GB). Rejected

In v1, migration cost is 91% the resource term (memory over link bandwidth), so host M and host GB correlate at 0.999. Dividing by GB instead of by M therefore changes almost nothing. At budgets where both rankings spend the whole budget (0.5x and 1x of the v1 operating point), the change moves Delta by at most 0.11 point. In v5 this will no longer hold, because migration cost gains a queue term and the budget is GB per day. The denominator ablation (W20) stays in the plan.

### H8: the baseline's within-host VM order. Rejected

v1 moves whole hosts, so only the one host at the edge of a GB budget can be split (22 VMs in the v1 world). Smallest-first, largest-first and random order change total cost by 0.014%. In v5, where the budget is spent VM by VM every day, the within-host order is a real design choice for P2 (W14).

## 4. Deviations from the pre-written rules

| Test | Pre-written rule gave | Final | Why |
| --- | --- | --- | --- |
| H4 | Confirmed (2.7-point move) | Rejected, using a fixed 5,116-host budget | The operating point moved with the weight, so the original test measured budget size, not cost spread |
| H6 | (rule unchanged) | Also computed at exactly matched budgets | The first run used v1's mismatched budgets, which mixed H3 into H6 |
| H7 | Inconclusive | Rejected, comparing denominators at 0.5x and 1x budgets | At 1x, BAM and the v1 rule select the same hosts (p * F > M is "positive BAM benefit"), so the original test could not show a denominator effect; at 2x BAM stops early, which measures the stopping rule |
| H5 | (rule unchanged) | Bug fix before the verdict was read | The first run computed migration days on the true p curve in noisy worlds, and a log-odds round trip at sigma = 0 broke ties; numbers under v1 accounting were unaffected |
| Labels | | | The Azure category is spelled "Unkown" in the trace; the first run matched nothing for H4 |

Each pre-written outcome is kept in the JSON (`pre_written_rule_*`) next to the final verdict.

## 5. What this changes for v2 (carried into protocol v0)

1. **Accounting must match the decision horizon.** A migration is credited only for failures within H days, the horizon of the p the policy sees. The v5 metric for unnecessary migrations already uses H days. The simulator must also let VMs depart (W10 `SIM_SPEC.md` has VM_ARRIVE and VM_DEPART events), so that a migration cannot protect VMs that would have left anyway.
2. **Budgets must be matched exactly, in the budgeted resource.** A threshold tuned by bisection over a lumpy hazard can miss the budget by 8%. P2 fills its budget to the GB, taking the remainder in a declared tie order, and any run that leaves more than a stated share of its budget unspent is reported.
3. **Stopping at negative expected benefit is only right under consistent accounting.** BAM's "fill while benefit > 0" wins under 30-day accounting and loses badly under v1's. The theory (W17) must state which accounting T2 assumes.
4. **Variance is small.** Over placements alone the SD of Delta is 0.06-0.33 point; over synthetic failure worlds it is 0.10-0.39 point. Both are far below the 1.6% bound for 30 seeds with Bonferroni correction. This is exploratory and from v1's simulator; the Week 14 pilot sets n.

## 6. Still open, and the week each closes

| Item | Closes |
| --- | --- |
| H1: calibration out of sample, with intervals, after a temporal split | Week 7 (R2) |
| H3: exact GB matching in v5's daily-budget simulator | Week 13 (v1 regression, G2) |
| Final verdicts combined with theory | Week 17 (THEORY.md, task 3) |
