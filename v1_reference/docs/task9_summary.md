# Task 9 — Experiments: When Does Cost-Sensitivity Actually Win?

## The question this answers

Task 8's fair (matched-budget) comparison found the cost-sensitive policy slightly *behind* a plain probability threshold, and traced this to random VM-to-host assignment making workload cost/criticality statistically independent of real hardware risk — removing any signal cost-awareness could exploit. This experiment tests the natural follow-up directly: **if workload importance actually correlates with hardware failure risk (as it plausibly does in real fleets — SLA-tiered hardware, legacy critical services left on aging infrastructure, newer capacity reserved for less-vetted workloads), does the cost-sensitive policy's advantage appear?**

## Method

A controlled rank-correlation sweep (a simplified Iman-Conover method): each VM gets a blended score — `rho × (criticality rank) + (1-rho) × (random draw)` — and is paired, in matching rank order, with a "host slot" ranked by that host's real model-group hazard level. At `rho=0` this reduces to task 8's uniform-random assignment (used as a continuity check); at `rho=1` it would be a strict rank-pairing of the most critical workloads onto the highest-risk hardware. The exact same replay simulator and matched-migration-budget comparison from task 8 is rerun at four correlation levels: 0.0, 0.3, 0.6, 0.9.

## Result

| target ρ | achieved rank-corr | missed failures (cost-sensitive) | missed failures (threshold, matched budget) | cost-sensitive advantage on total cost |
|---|---|---|---|---|
| 0.0 | -0.00 | 5,499 | 5,311 | **-3.1%** (behind — replicates task 8) |
| 0.3 | 0.31 | 5,335 | 5,311 | **+0.3%** (roughly tied) |
| 0.6 | 0.73 | 5,243 | 5,310 | **+2.0%** |
| 0.9 | 0.86 | 5,141 | 5,254 | **+3.4%** |

Two things move monotonically and cleanly with ρ: the cost-sensitive policy's total-cost advantage over the matched-budget threshold rises from -3.1% to +3.4% as correlation increases, **and** its raw missed-failure count actually falls (5,499 → 5,141) while the threshold's stays roughly flat (~5,310) — so the improvement isn't just a reweighting artifact, cost-sensitivity genuinely starts catching more real failures once there's a real relationship for it to exploit. **The crossover happens around ρ ≈ 0.3** — a fairly modest correlation, not an extreme or contrived one.

## What this establishes

The project's hypothesis, honestly stated, is now **conditional rather than unconditional**: a workload-aware, cost-sensitive mitigation policy outperforms probability-threshold mitigation specifically *when workload criticality correlates with hardware failure risk* — and the threshold for that condition to matter (ρ ≈ 0.3) is low enough to be plausible in real infrastructure. When workload placement is genuinely independent of hardware risk (task 8's finding), a simple probability threshold is equally good or slightly better, because there's nothing for cost-awareness to correctly weight.

This is a stronger, more credible, and more falsifiable claim than "our policy always wins" would have been — it says exactly under what condition the mechanism works, backed by a monotonic dose-response result rather than a single anecdotal comparison. It also comes with an honest limitation: whether real Azure-scale fleets actually operate at ρ ≥ 0.3 between workload importance and hardware risk is an open empirical question this project cannot answer directly — no public dataset links the two (the same constraint documented in `project_scope.md` §5) — so this result should be read as "the mechanism works once this condition holds," not as proof the condition holds in production today.

## Output

- **`data/processed/correlated_assignment_sweep.csv`** — full results at all four ρ levels, including achieved correlation, migration counts, and both missed-failure and total-cost comparisons.
- `scripts/07_correlated_assignment_experiment.py` — rerunnable (~25s), same simulator core as task 8 for direct comparability.

## Feeds into next

Task 10 (results write-up) can now tell the full, honest arc: naive comparison suggested a win → fair comparison showed it wasn't real under independence → the follow-up experiment identifies exactly the condition (ρ ≳ 0.3) under which the win is real, with a clean supporting curve. That arc is a stronger project narrative than a single flattering number would have been.
