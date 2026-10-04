# Criticality mapping: Google 2019 trace → v1's three tiers (Week 6)

Fixed before any trace data is read (Week 8 computes ρ with it). Sources:
- the trace documentation "Google cluster-usage traces v3" (Wilkes, revised 2020-08-18), section "Collections and instances";
- the format file `clusterdata_trace_format_v3.proto` in github.com/google/cluster-data;
- Tirmazi et al., EuroSys 2020 (`reading/tirmazi2020borg.md`).

## Target: v1's tiers

v1 maps the Azure V1 VM category to three tiers (`scripts/01_preprocess.py`):

| v1 tier | Azure V1 category | Weight | Share of v1's 2,013,767 VMs |
| --- | --- | --- | --- |
| high | Interactive | 1.0 | 3.0% |
| medium | Unknown (spelled "Unkown" in the trace) | 0.6 | 58.2% |
| low | Delay-insensitive | 0.3 | 38.8% |

The weights are v1's choices, not measured costs. They stay as they are so that Google-based results can be compared with v1. The rank correlation in `rho_definition.md` uses only their order, so the exact values do not affect ρ̂.

## Trace fields used

Both fields are on every instance event (`instance_events`), and tasks inherit them from their job:

- `priority`: an integer from 0 to 450; larger means more important. The documented tiers are:
  - free tier: ≤ 99;
  - best-effort batch (beb): 100-115;
  - mid-tier: 116-119;
  - production: 120-359;
  - monitoring: ≥ 360.

  These ranges are from the trace documentation. Tirmazi et al. print beb as 110-115, and the documentation says that is a mistake.
- `scheduling_class`: 0-3, from "most insensitive" (best effort) to "most sensitive" to latency. The documentation describes 3 as serving revenue-generating user requests and 0 as non-production work. It is not a priority: priority decides whether something is placed, and scheduling class decides how the machine treats it once placed.

A task's priority or scheduling class can change while it runs (UPDATE_RUNNING events). The rule: take the value from the SCHEDULE event that placed the task on the machine. An UPDATE_RUNNING event later in the same placement replaces it from that time on, which only matters for the time-weighted variant.

## Primary mapping M1: by priority tier

| Trace | v1 tier | Reason |
| --- | --- | --- |
| production (120-359) and monitoring (≥ 360) | high (Interactive) | Production "requires high availability (e.g., user-facing service jobs ...)" (Tirmazi, section 1). Monitoring is merged with production, as in Tirmazi et al. |
| mid-tier (116-119) | medium (Unknown) | Its SLOs sit between free and production. It is the middle tier both by definition and by role |
| free (≤ 99) and best-effort batch (100-115) | low (Delay-insensitive) | No SLOs. Batch work managed by a queueing scheduler is what Azure calls delay-insensitive |

## Alternative M2: by scheduling class

| scheduling_class | v1 tier |
| --- | --- |
| 3 and 2 (sensitive, most sensitive) | high |
| 1 (insensitive, "often used for batch") | medium |
| 0 (most insensitive, best effort) | low |

Reason: Azure's category describes how latency-sensitive the workload is, not how the scheduler ranks it. Scheduling class is the trace field closest in meaning to that.

## Alternative M3: strict joint mapping

| Condition | v1 tier |
| --- | --- |
| production or monitoring, **and** scheduling class ≥ 2 | high |
| free or best-effort batch, **and** scheduling class ≤ 1 | low |
| everything else | medium |

Reason: "high" is kept for work that is both important to the scheduler and latency-sensitive. Mixed cases are treated as the trace's equivalent of Azure's "Unknown".

## What counts as a workload

- **Tasks only** (`collection_type = 0`, jobs). Alloc instances (`collection_type = 1`) are resource reservations: the tasks running inside them already appear as their own instances, with `alloc_collection_id` set. Counting both would double-count. Tirmazi et al. report that 95% of jobs in allocs are production, so the double count would inflate "high".
- **Placements on dedicated machines are excluded.** Their `machine_id` is the special dedicated value (−1 in the format file), and those machines are absent from `machine_events`.
- One task can be placed several times (evicted, then rescheduled). Each (task, machine) placement is one observation (`rho_definition.md`).

## Sensitivity rule (Week 8)

ρ̂ is reported under M1, M2 and M3. If its sign changes between mappings, the G1 decision note says so in its first paragraph. The G1 class is assigned with M1 only, because M1 is written down here first and the protocol forbids choosing the mapping after seeing the result.

## Checks to run on the first pilot query (Week 8)

1. The tier shares by placement and by task-hours, per cell. Tirmazi's Figure 3 gives usage shares by tier, for comparison.
2. The share of "high" under M1. If it is far from v1's 3%, the regimes in `PROTOCOL.md` section 3 still use measured shares (regime B2 is "as measured"); record the share in the scenario card.
3. Event type codes. SCHEDULE = 3, EVICT = 4, FAIL = 5, FINISH = 6, KILL = 7, LOST = 8 and the other instance codes are from the format file. For machine events, ADD = 1, REMOVE = 2 and UPDATE = 3, also from the format file. Check them against the counts on the first query: for example, ADD events at time 0 should be roughly one per machine.
