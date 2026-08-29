# Task 5 — Workload Criticality & Migration Cost: Results

## What's new vs. task 2

Task 2 already gave criticality tiers (from Azure's real `vm_category`) and a placeholder migration-cost proxy (a linear combination of memory + vCPU count). This task replaces that placeholder with an actual **migration-cost model**, grounded in the standard pre-copy live-migration formula from the systems literature (Clark et al., *Live Migration of Virtual Machines*, NSDI 2005): pre-copy duration ≈ memory size / (network bandwidth − dirty-page rate), and it only converges if the VM doesn't dirty memory faster than the link can copy it.

**What's real data vs. modeling assumption, stated plainly:** `memory_gb`, `vcores`, and `avg_cpu` are real, per-VM, from the Azure trace. The *parameters* that turn those into a migration duration — network bandwidth, how fast a fully-busy VM dirties memory, the fallback pause if pre-copy never converges, and how long an unmitigated hardware failure takes to recover from — are modeling assumptions from published ranges, since no public dataset exposes Azure's actual live-migration network telemetry or incident-recovery times. Each is named as a constant at the top of the script with its rationale, specifically so it can be challenged or swept in a sensitivity check rather than being buried inside the math:

| Assumption | Value | Rationale |
|---|---|---|
| Migration network bandwidth | 1,250 MB/s (~10 Gbps) | Typical modern datacenter inter-host fabric |
| Max memory dirty-rate at 100% CPU | 150 MB/s | Mid-range of the tens-to-a-few-hundred MB/s reported for write-heavy workloads in the live-migration literature |
| Stop-and-copy fallback pause | 60 s | Bounded worst case if pre-copy never converges (consistent with Hyper-V/VMware's bounded pre-copy round budget) |
| Unmitigated failure recovery time | 10 min | No public ground truth exists for this; treated explicitly as a sensitivity parameter, not a measured constant — worth stress-testing in task 9 |

## Two migration costs, kept separate on purpose

- **Customer-facing cost** (`migration_customer_cost_min`): the brief final stop-and-copy blackout — sub-second when pre-copy converges, up to 60s if it doesn't — weighted by criticality.
- **Infra resource cost** (`migration_resource_cost_min`): the *entire* pre-copy duration, which doesn't interrupt the VM but does occupy source/destination host bandwidth — this is what makes an unnecessary migration wasteful even when the customer never notices it.

## Key finding: at real Azure workload intensity, live migration essentially always converges

100% of the 2,013,767 VMs converge under pre-copy (median real `avg_cpu` is only 10.5%, far below what it would take to outrun a 1,250 MB/s link at the assumed 150 MB/s max dirty-rate). Practically, that means: **the customer-facing cost of migrating is negligible and nearly uniform across the whole fleet** (everyone gets the ~1-second blackout case). The migration cost that actually *varies* meaningfully between VMs is the resource cost, which scales with VM size:

| size tier | mean resource cost (min) | median | max |
|---|---|---|---|
| small | 0.032 | 0.025 | 0.230 |
| medium | 0.236 | 0.192 | 0.899 |
| large | 1.533 | 1.529 | 1.721 |

A ~50x spread from smallest to largest VM — this is the term that should make the cost-sensitive policy (task 6) reluctant to migrate a large VM on a marginal failure signal, even though every migration is customer-safe.

## Failure cost, by criticality tier

| criticality | mean cost if unmitigated (customer-impact-min) | VMs |
|---|---|---|
| high (Interactive) | 10.0 | 60,682 |
| medium (Unknown) | 6.0 | 1,172,597 |
| low (Delay-insensitive) | 3.0 | 780,488 |

## A sanity check, and an honest caveat about it

The script asserts that failure cost is always far larger than migration's customer-facing cost (it came out to a constant 600x for every single VM). That check is real but limited: because both quantities are scaled by the *same* criticality weight, that weight cancels out of the ratio algebraically — so 600x confirms the two constants are self-consistent (a false-positive migration is cheap relative to a real failure, for every VM equally), but it isn't evidence of meaningful *variation* across VMs. The column that actually varies and will drive task 6/8's "unnecessary migration" trade-off is `migration_resource_cost_min`, not the customer-facing cost — flagging that distinction now so it isn't mistaken for more than it is.

## Output

- **`data/processed/azure_vms_with_costs.csv.gz`** (2,013,767 rows, 24 columns) — adds `precopy_converges`, `migration_time_est_s`, `migration_blackout_s`, `migration_customer_cost_min`, `migration_resource_cost_min`, `failure_customer_cost_min` on top of everything from task 2.
- `scripts/04_workload_criticality_cost.py` — rerunnable (~15s), assumption constants at the top for easy sensitivity testing.

## Feeds into next

Task 6's decision rule now has everything it needs on a common per-VM basis: `p_fail_within_window` and `expected_ttf_days` (tasks 3–4), `criticality_weight` (task 2), and `migration_resource_cost_min` / `failure_customer_cost_min` (this task). The remaining work is purely the comparison logic — no new data or modeling.
