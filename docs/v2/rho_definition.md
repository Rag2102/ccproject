# Empirical ρ: definition (Week 6)

Target: a collaborator can compute ρ̂ from the Google 2019 trace by following this note alone. Fixed before the data is read; Week 8 runs it (`scripts/v2/13_trace_rho.py`), and gate G1 classifies the result (`PROTOCOL.md` section 7).

## What ρ measures

v1's simulator assigns VMs to hosts at random (ρ = 0), then sweeps a correlation ρ between how critical a VM is and how risky its host is. The threshold-vs-BAM crossover sits near ρ ≈ 0.3 (provisional pH). **Empirical ρ asks where real placement sits on that axis:** in a production cluster, do critical workloads run on riskier machines (ρ > 0), on safer ones (ρ < 0), or neither?

## Data

- **Trace:** Google ClusterData 2019 (8 cells, May 2019, CC-BY 4.0; entry in `data_sources.md`).
- **Tables:** `instance_events` and `machine_events`, plus `machine_attributes` if a platform or age proxy is needed.
- **Not used:** `instance_usage` (3.4 TB of Parquet for 8 cells) is not needed.
- **Access:** BigQuery, or a free download from the public buckets `gs://clusterdata_2019_<cell>/` (Parquet).
- **Size:** about 21 GB for cell a and 176 GB for all eight cells. The plan is to download one cell at a time, aggregate it, and delete the raw files. That avoids BigQuery scan charges altogether.

## Step 1: placements

For each cell:

1. From `instance_events`, keep job tasks (`collection_type = 0`) and drop dedicated machines (`machine_id = −1`).
2. A placement starts at a SCHEDULE event (type 3) on machine m. It ends at the next EVICT, FAIL, FINISH, KILL or LOST event (types 4-8) of the same task (collection_id, instance_index), or at the end of the trace.
   - Times are microseconds from 600 s before the start of the trace window.
   - Time 0 means "before the trace"; clip it to the window start.
   - 2^63 − 1 means "after the trace"; clip it to the window end.
3. A placement's criticality comes from `criticality_mapping.md` (M1 primary). Its tier score is 2 (high), 1 (medium) or 0 (low).
4. Placements that overlap a window w (below) count in w. Weight w_i: 1 per placement (**primary**), or hours resident in the window (variant).

## Step 2: windows

- Seven-day windows: days 1-7 (warm-up only: risk proxies are estimated here, ρ is not computed), then 8-14, 15-21 and 22-28. Days 29-31 are dropped (partial window).
- Variant: one-day windows from day 8 on, for the time-series plot.

## Step 3: host risk proxies (fixed now, computed in Week 8)

Neither proxy is a hardware failure: see the threats below. Each proxy is computed only from data **before** window w, so the risk score does not use events that the placement itself might cause.

Machine event types: ADD = 1, REMOVE = 2, UPDATE = 3. A **long removal** is a REMOVE event not followed by an ADD of the same machine within 24 hours; a **short removal** is any other REMOVE. Tirmazi et al. report a forced OS upgrade about once a month per machine. Short removals are taken to be maintenance, and long removals are the failure-like part.

| Proxy | Definition | Use |
| --- | --- | --- |
| (a) Platform rate | For machine m on platform k: long removals per machine-day on platform k, over all days before window w | **Primary.** Many machines share a platform, so the rate is stable. It has ties: about 7 platforms per trace |
| (b) Machine history | For machine m: a Kaplan-Meier style hazard of long removal using m's own events before w, shrunk towards its platform rate (empirical Bayes, beta-binomial on machine-days) | Secondary. Machine-specific, but noisy over 7-28 days |

Variants reported but not used for G1:
- (a′) counts all removals, short and long;
- (c) a capacity-normalised age proxy from `machine_attributes`, if one exists. To be checked; the attribute names are obfuscated.

## Step 4: the statistic

For each cell c and window w, over all placements i in that window:

- **Kendall's τ-b** (primary) between the tier score s_i ∈ {0, 1, 2} and the host risk r_{m(i)}.
- **Spearman's ρ_s** with ties handled by mid-ranks (tie-corrected), as a second statistic.
- Both are needed because:
  - the tier score has only 3 values;
  - proxy (a) has only about 7;
  - ties dominate, and τ-b is the statistic designed for that.
- Weighting: with w_i = 1, every placement counts once. The time-weighted variant uses weighted ranks.

Pooled estimate per cell: the mean over windows 8-14, 15-21 and 22-28. Across cells: report each cell, then the median over cells. **G1 uses the per-cell values:** a class holds only if it holds in the majority of cells analysed, and all cells are shown. The rule, including what happens without a majority (class B), is in `PROTOCOL.md` section 7 (v0.1, confirmed 4 Oct 2026).

Also report a **dispersion** measure: the Gini coefficient of the share of high-tier placements across machines (0 means spread evenly). The plan asks for it because ρ ≈ 0 can hide strong clustering.

## Step 5: uncertainty

- **Cluster bootstrap over machines:** 2,000 resamples. Draw machines with replacement, take all of each drawn machine's placements in every window, and recompute the per-cell estimate.
- **Interval:** BCa, falling back to the percentile interval if the acceleration estimate is unstable; say which one was used.
- Placements on the same machine share the same risk value and are not independent, so resampling placements would make the interval too narrow.

## Step 6: from ρ̂ to the simulator's axis (made precise 4 Oct 2026, before any estimate)

**What 0.30 means.** v1's sweep (`scripts/07_correlated_assignment_experiment.py`) reports its achieved correlation as the tie-corrected Spearman between VM criticality weight (3 levels) and host risk score (16 levels), across VMs. The break-even pH = 0.30 is therefore a Spearman value **under v1's margins**:
- tier shares 38.8 / 58.2 / 3.0% (low / medium / high);
- v1's distribution of host risk.

A rank correlation's range depends on its margins, so the same statistic computed on Google placements is not on the same scale.

**Common axis.** Both are put on the latent Gaussian-copula ρ_L:
- **The threshold:** pH_L is the ρ_L at which a Gaussian copula with v1's margins gives Spearman 0.30. It is computed exactly from bivariate normal cell probabilities, without simulation noise. **pH_L = 0.375.**
- **The C0/C1 boundary:** 0.20 is converted the same way.
- **Each cell:** ρ̂_L is the ρ_L at which a Gaussian copula with **that cell's** margins (placement-weighted tier shares and risk distribution) gives the observed τ-b. The CI endpoints are mapped the same way; the curve is monotone.
- **G1** compares ρ̂_L's interval with pH_L.

The curve replaces the "provisional curve (W11)" for G1. Week 11 may refine it for the simulator but cannot re-classify (`PROTOCOL.md` section 7).

**Also reported:** the direct reading, Google's tie-corrected Spearman against 0.30. It ignores the margin difference and is shown for transparency only.

**Details fixed with this step:**
- A removal counts towards window w's proxy only if its 24-hour follow-up ends before the window starts, so whether it is long is known by then.
- BCa acceleration uses a grouped jackknife over 100 random machine groups, because a full jackknife over about 12,000 machines is too slow. If the bias correction is not finite, or |a| > 0.25, the percentile interval is used, and the table says which interval each row uses.
- Risk proxy (b) uses gamma-Poisson shrinkage with the prior strength set by the method of moments within each platform.

## Threats to validity

| Threat | What it does | What we do |
| --- | --- | --- |
| Removals are not hardware failures | Removals include upgrades, repairs, drains and capacity moves | Use long removals only for the primary proxy; report (a′) as a sensitivity; caption every figure "removal proxy, not failure" |
| Platform mix confounds age | Newer platforms may host more production work *and* have different removal rates for reasons of age, not risk | Report ρ within platform (stratified τ-b) next to the pooled value |
| Priority reflects scheduler policy | Borg protects production work from eviction (fewer than 0.2% of production collections are evicted). Any ρ partly measures the scheduler's choices | This is the quantity we want (where critical work actually runs), but it does not carry over to a scheduler without that policy. Say so |
| Short trace | 31 days. Few long removals per machine, so proxy (b) is noisy | Proxy (a) is primary; (b) is shrunk |
| Tasks are not VMs | Borg tasks are short and many; Azure VMs (v1's median life about 40 min) are closer than one would think, but tiers differ | The rank-based statistic uses only the order of the tiers; tier shares are recorded per cell |
| Dedicated machines and allocs | Dedicated placements are hidden; allocs would double-count | Exclude both (`criticality_mapping.md`) |
| Mapping choice | M1, M2 and M3 give different tiers | M1 decides G1; M2 and M3 are sensitivity checks; a sign change is reported first |
| Cell differences | Workload mix differs by cell (Tirmazi, section 4) | Per-cell results; majority rule |

## Fallback (from the plan)

If the Google trace gives no usable risk proxy, for example too few long removals to rank platforms, Week 8 uses the Alibaba 2018 trace (about 4,000 machines over 8 days, per Tirmazi et al.; whether its machine table records failures is to be checked) or the measured tier mix only. That outcome is G1 class D.
