# Tirmazi et al., Borg: the Next Generation (EuroSys 2020)

Source read: the authors' copy (CMU), the whole paper, pages 1-14, plus the trace documentation "Google cluster-usage traces v3" (Wilkes, revised 2020-08-18) sections on machines, events, priorities and access, and the schema files in the `clusterdata_2019_schema` bucket.

| Field | Notes |
| --- | --- |
| Problem | Describe the May 2019 Borg trace and compare it with the 2011 trace. |
| Data | 8 cells, 31 days, 96.4k machines (about 12k per cell), 7 hardware platforms, 21 machine shapes, priorities 0-450 (Table 1). 2.8 TiB in all. |
| Baseline | The 2011 trace (1 cell, 12.6k machines). |
| Metric | Usage and allocation by tier; scheduling delay; job resource-hours (C² over 23,000; Pareto α ≈ 0.7). |
| Claim | Work moved from the free tier to best-effort batch. The top 1% of jobs use over 99% of resources. Memory is now over-committed as much as CPU. Most "failures" in 2011 analyses were user or parent kills (section 5.2). |
| Limitation | Descriptive only. No machine failures as such: the trace has machine REMOVE events and instance EVICT events, both of which mix failures with maintenance. |
| What we reuse | The priority tiers (below), the event definitions, and the scale needed for the ρ bootstrap (about 12k machines per cell). |
| Reviewer would say | "Removal is not failure, and Borg already places production work to avoid eviction, so a correlation between priority and machine risk partly measures the scheduler's policy." Both points go into the threats list (`docs/v2/rho_definition.md`). |

## Facts that set the Week 6 definitions

- **Tiers (2019 values; the trace documentation, which corrects the paper):** free ≤ 99; best-effort batch 100-115 (the paper says 110-115, which the documentation calls a mistake); mid 116-119; production 120-359; monitoring ≥ 360. The paper merged monitoring into production; `criticality_mapping.md` does the same.
- **Evictions are rarely hardware.** An eviction may come from "a (rare) hardware failure, or a forced OS upgrade (about 1/month per machine)", preemption or over-commit (section 5.2). Only 3.2% of collections see any eviction, 96.6% of them below priority 120, and fewer than 0.2% of production collections.
  - So instance evictions are not a usable host-failure label.
  - The risk proxy must come from machine events, and even REMOVE includes monthly maintenance. `rho_definition.md` therefore separates short removals (the machine is re-added soon) from long ones.
- **Alloc sets.** 2% of collections, but 20% of CPU and 18% of RAM allocations; 95% of jobs in allocs are production (section 5.1). Counting both an alloc instance and the tasks inside it double-counts production placements. Rule: count job tasks only.
- **Cells differ a lot.** Cell a has the most production work, cell b the most best-effort batch, cell h the most mid-tier (section 4). ρ is reported per cell, never only pooled.
- **Dedicated machines** are omitted from machine events, and tasks on them get a special machine ID (trace documentation; −1 in the format file). Exclude those placements.

Citation: `tirmazi2020borg` in `paper/refs.bib` (DOI 10.1145/3342195.3387517 from the paper's first page).
