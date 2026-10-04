# Tasks 6 & 7 — Cost-Sensitive Policy & Threshold Baseline: Results

Built and validated together since the baseline is a strict subset of the cost-sensitive policy's inputs (same `p_fail`, ignoring TTF/criticality/cost entirely) — there's no meaningful way to design one without the other in hand for comparison.

## The decision rule (`scripts/policy.py`)

**Cost-sensitive policy:** migrate iff `p_fail × failure_cost × urgency(ttf) > migration_cost`.

- `failure_cost` and `migration_cost` are already on a common customer-impact-minutes scale and already criticality-weighted (task 5), so the comparison itself stays a plain expected-cost inequality.
- `urgency(ttf)` is the one genuinely new mechanism: if expected TTF already exceeds the 30-day decision lookahead, urgency sits at a neutral 1.0 — the risk is already fully reflected in `p_fail_within_window` itself, and inflating it further would double-count the same signal. If TTF is *shorter* than the lookahead, urgency scales up (capped at 5x) — the reasoning being that a failure expected imminently leaves no room to defer the decision to a future reassessment cycle, so the same probability should be taken more seriously.

**Baseline:** migrate iff `p_fail > τ`, full stop. τ is set to the 95th percentile of `p_fail_within_window` across every real host-risk state in the task 3/4 lookup table (τ ≈ 0.0073) — "flag the riskiest 5% of observations," a standard ops heuristic, rather than a number picked to make the comparison look good. Task 9 will additionally sweep τ explicitly, since any single fixed threshold is somewhat arbitrary by construction — that arbitrariness is part of what this project is arguing against.

## Verification, part 1: hand-built scenarios

Five cases built to have a known right answer, checked against both policies:

| scenario | cost-sensitive | threshold (τ=0.005) | agree? |
|---|---|---|---|
| Obvious migrate (high risk, imminent, critical, cheap) | MIGRATE | MIGRATE | yes |
| Obvious skip (negligible risk, distant, batch) | wait | wait | yes |
| TTF-awareness: modest p_fail, but imminent | MIGRATE | MIGRATE | yes |
| **Cost-awareness: p_fail just above τ, but huge low-criticality VM, distant failure** | **wait** | **MIGRATE** | **no** |
| Criticality-awareness: same p_fail, but critical + cheap to move | MIGRATE | MIGRATE | yes |

The one designed disagreement fires exactly where intended: at identical `p_fail` (0.006, just over τ), the threshold policy migrates a large, low-criticality VM with a distant expected failure purely because the probability crossed a line — spending 1.5 minutes of real migration resource cost to avert an expected 0.018-minute cost of inaction. The cost-sensitive policy declines. This is the project's thesis in miniature.

## Verification, part 2: the full decision surface

Before building the temporal replay simulator (task 8), every real host-risk state from the task 3/4 lookup table (1,584 states) was crossed with every real representative VM cost profile (9 size×criticality buckets built from real Azure cost data, task 5) — 14,256 combinations covering the actual state space this fleet can be in, evaluated once, no simulation needed yet:

- **95.92% agreement** between the two policies — most states are either obviously safe or obviously urgent regardless of which policy is asked, which is expected and reassuring (the cost-sensitive policy isn't wildly different everywhere, only where it should be).
- **0.79% of states: cost-sensitive migrates, threshold doesn't.** These skew heavily toward small, high-criticality VMs (80% high-criticality, 100% small) sitting just under τ — cases where the flat probability threshold under-reacts to a genuinely important workload because criticality isn't in its vocabulary at all.
- **3.28% of states: threshold migrates, cost-sensitive doesn't.** These skew toward large/medium VMs across a mix of criticality levels, at a distant expected failure (mean TTF ≈ 4,845 days) — the exact "expensive, low-urgency, gets migrated anyway" pattern the project's hypothesis predicts a flat threshold will produce.

That the *threshold-migrates-unnecessarily* bucket (3.28%) is over 4x larger than the *cost-sensitive-catches-something-missed* bucket (0.79%) is an early, encouraging signal for the project's core claim (fewer unnecessary migrations without giving up protection on critical workloads) — but this is a static state-space comparison, not a measurement of actual outcomes over time. Task 8's replay simulator is what turns "the policies disagree here" into "and here's what actually happened to real drives when they did."

## Output

- **`scripts/policy.py`** — the two decision functions, imported (not reimplemented) by the task 8 simulator, so the policy that's tested is exactly the policy that was designed.
- `scripts/05_policy_design.py` — scenarios + decision surface, rerunnable (~5s).
- `data/processed/policy_scenarios.csv`, `data/processed/policy_decision_surface.csv`.

## Feeds into next

Task 8 builds the day-by-day replay: assign real VMs onto real Backblaze-drive-modeled hosts, run both policies forward through each host's actual health trajectory, and score customer-impacting failures avoided vs. unnecessary migrations triggered — turning this state-space comparison into the actual headline result.
