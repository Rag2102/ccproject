# Task 8 — Replay Simulation & Evaluation: Results

## The simulator

Not a general cloud simulator (see `project_scope.md` §6 for why CloudSim/SimGrid would be the wrong tool). This is a purpose-built replay: 122,618 real Backblaze drives are hosts; 2,013,767 real Azure VMs are assigned to them uniformly at random, once, identically for both policies (there's no public dataset linking real VM placement to real host failures — see `project_scope.md` §5 — so this is the unbiased default, and fairness only requires both policies see the same mapping, which they do). Each host walks forward through its *actual* real health trajectory in 30-day steps; both policies decide migrate/wait at every step using only the hazard/TTF lookup values available at that step; a host's real fate (whether/when it failed) is a fixed fact from the data, since migrating workloads off a host doesn't change whether the physical hardware itself fails.

Four possible outcomes per host per policy: **necessary migration** (migrated, host would have failed), **customer-impacting failure** (never migrated in time, host failed), **unnecessary migration** (migrated, host never actually failed), **correct inaction** (never migrated, host never failed).

## Result 1: the naive comparison (and why it's not the fair one)

| metric | cost-sensitive | threshold (τ=0.0073, 95th pct.) |
|---|---|---|
| customer-impacting failures | 5,493 | 4,872 |
| unnecessary migrations | 3,697 | 5,940 |
| total migrations | 5,116 | 7,980 |
| total cost impact (customer-minutes) | 456,533 | 410,867 |

Taken at face value this looks bad for the cost-sensitive policy — more missed failures, higher total cost. But look at the migration counts: 5,116 vs 7,980. **These two policies are operating at very different overall aggressiveness levels**, which is an artifact of how task 5's cost constants happen to be calibrated (aggregating ~16.4 VMs per host puts typical `failure_cost_host` around 81 customer-minutes against `migration_cost_host` around 1.4 — a ~58x ratio that implies an effective break-even probability around 0.017, stricter than the baseline's independently-chosen τ=0.0073). Comparing two policies at two different, independently-chosen operating points isn't a test of which one *targets better* — a stricter policy will always look worse on raw miss-count and better on migration-count, trivially, regardless of how smart its targeting is.

## Result 2: the fair comparison — matched migration budget

The right test: give both policies the **same number of total migrations** and see which one spends that budget on the hosts that actually needed it. (Standard practice for comparing tunable classifiers/policies — e.g. comparing at matched recall rather than at two arbitrary thresholds.) τ was swept to find the threshold whose migration count lands closest to the cost-sensitive policy's 5,116 (the achievable counts jump in large discrete steps — many hosts share the same model-group/age hazard value — so an exact match isn't achievable; 5,522 was the closest, ~8% over rather than under).

| metric | cost-sensitive (5,116 migrations) | threshold, matched budget (5,522 migrations) |
|---|---|---|
| customer-impacting failures | 5,493 | 5,311 |
| necessary migrations | 1,419 | 1,601 |
| unnecessary migrations | 3,697 | 3,921 |
| total cost impact (customer-min) | 456,533 | 442,701 |

**At a matched budget, the plain probability threshold comes out about 3.1% ahead on total cost, and catches more real failures.** This is the honest headline of task 8, and it does not confirm the project's hypothesis as currently instantiated. Reporting it as a win would misrepresent the experiment.

## Why — and what it means, not just that it happened

A follow-up check makes the mechanism visible: splitting the 6,912 real failures into cost quartiles (by `failure_cost_host`) and checking each policy's miss rate per quartile shows **no sign that cost-sensitivity better protects the highest-cost failures** — miss rate rises slightly across quartiles for all three variants (cost-sensitive, threshold, threshold-matched) at roughly the same slope. The likely reason is structural, not a bug: **VMs were assigned to hosts uniformly at random, which makes workload cost/criticality statistically independent of a host's actual hardware failure risk.** When cost and risk are uncorrelated, re-weighting a fixed migration budget by cost can only add noise relative to pure probability-ranking — there is no exploitable relationship for cost-awareness to find, by construction of this experiment. Pure risk-ranking is close to the theoretically best way to spend a fixed budget precisely *when* cost carries no information about who's actually going to fail.

This reframes rather than invalidates the project. Two follow-ups worth running in task 9, both cheap given the simulator already exists:

1. **A correlated-assignment scenario.** Real fleets plausibly do correlate workload importance with hardware characteristics (SLA-tiered placement, critical workloads kept off older/cheaper hardware, etc.) — that correlation is exactly the condition under which cost-aware targeting should have room to help, and this experiment specifically tested the condition (independence) under which it can't. Re-running with a deliberately correlated VM→host assignment is a direct, honest test of that hypothesis.
2. **Reframe what "cost-sensitive" is supposed to win at.** This result suggests the value of TTF/cost/criticality-awareness may lie less in *re-ranking within a fixed budget* and more in *choosing the right overall aggressiveness adaptively* (e.g. tightening up when aggregate fleet risk or cost exposure is elevated) — something a single fixed τ structurally cannot do. Task 9's sensitivity sweep should test this framing directly rather than only re-testing the current per-host rule at more operating points.

## Output

- **`data/processed/simulation_results_per_host.csv`** (122,618 rows) — every host's outcome and cost under all three policy variants (cost-sensitive, threshold, threshold-matched).
- **`data/processed/simulation_headline_summary.csv`** — the naive-comparison table.
- `scripts/06_simulation_evaluation.py` — rerunnable (~30s), includes the matched-budget sweep and cost-quartile diagnostic inline.

## Feeds into next

Task 9 (experiments) now has a concrete, falsifiable question to chase rather than a foregone conclusion to report: does a correlated-assignment scenario, or a reframed "adaptive aggressiveness" version of the policy, recover the advantage the naive comparison suggested but the fair one didn't confirm?
