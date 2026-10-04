# Gate G1: where does real placement sit? (Week 8)

Status: **draft for your sign-off**, 4 Oct 2026 (ahead of the calendar; the card is 23-29 Nov 2026). Under `PROTOCOL.md` section 7, the class assigned here is final once you sign it off. The Week 17 break-even replaces pH for interpretation only, never for re-classification.

**Decision proposed: class C0 (below, negligible).** The class is C0 in each of the three cells, so the majority is C0.

**Sign change, reported first as `rho_definition.md` requires.** The sign of the correlation changes with the choice of tier mapping and risk proxy. In cell a it is −0.009 under the primary mapping M1 and +0.016 under M2; cell h's per-machine proxy gives negative values where its platform proxy gives positive ones. The magnitude does not change with any choice: across all 30 combinations of cell, mapping, proxy and weighting, |τ-b| ≤ 0.075 and the upper bound on the latent axis is ≤ 0.082. The conclusion, that critical work is essentially uncorrelated with machine risk, holds under every choice. Its direction does not.

Numbers: `results/v2/trace_rho.json`, `results/v2/trace_rho_table.csv`. Figure F3 draft: `results/figures/v2_trace_rho.pdf`. Code: `scripts/v2/13_trace_rho.py` (commits bb4293f and 198b202). Method: `rho_definition.md`, fixed before any data was read.

## 1. What was measured

- **Data:** Google ClusterData 2019, cells a, b and h. They were chosen before any data was read as the cells Tirmazi et al. report with the most production, best-effort batch and mid-tier work, to span workload mixes.
- **Placements:** every job task's SCHEDULE on a machine, until its next end event; dedicated machines and allocs excluded.
- **Windows:** days 8-14, 15-21 and 22-28; days 1-7 are warm-up.
- **Criticality (M1):** production and monitoring tiers are high, mid-tier is medium, free and best-effort batch are low (`criticality_mapping.md`).
- **Risk (primary proxy):** each machine's platform rate of *long* removals (removals not followed by re-addition within 24 hours) per machine-day, using only removals whose 24-hour follow-up ended before the window. **This is a removal proxy, not a failure rate.**
- **Statistic:** Kendall's τ-b, pooled over the three windows. Uncertainty from a 2,000-resample bootstrap over machines, BCa intervals.
- **Comparison:** each value is mapped to the latent Gaussian-copula axis under that cell's own margins. There it is compared with pH_L = 0.375 (v1's break-even Spearman of 0.30, converted under v1's margins) and with the C0/C1 boundary 0.251 (0.20 converted the same way).

| Cell | Machines | Placements per window (millions) | Dedicated schedules excluded | High-tier share of placements (M1) |
| --- | --- | --- | --- | --- |
| a | 9,949 | 71.0 / 63.6 / 69.4 | 26,514 | 21.2% |
| b | 10,023 | 61.0 / 64.3 / 70.5 | 623 | 6.4% |
| h | 11,511 | 57.1 / 57.9 / 61.8 | 5.4 million | 19.4% |

## 2. Result (M1, primary proxy, placement-weighted)

| Cell | τ-b [95% CI] | Spearman [95% CI] | Latent ρ_L [95% CI] | Class |
| --- | --- | --- | --- | --- |
| a | −0.009 [−0.011, −0.007] | −0.010 [−0.012, −0.008] | −0.015 [−0.019, −0.011] | C0 |
| b | 0.003 [−0.004, 0.010] | 0.003 [−0.005, 0.010] | 0.007 [−0.009, 0.022] | C0 |
| h | 0.015 [0.007, 0.032] | 0.016 [0.009, 0.036] | 0.027 [0.013, 0.056] | C0 |

- **Class rule** (`PROTOCOL.md` section 7): C0 if the CI upper bound is below the C0 boundary. The highest upper bound, 0.056 (cell h), is below 0.251 by a factor of 4.5 and below pH_L by a factor of 6.7. No CI is wider than 0.30, so none counts as unresolved.
- **Majority rule:** three of three cells are C0, so G1 = C0.
- **Median over cells:** τ-b 0.003, ρ_L 0.007.
- **Direct reading,** Google's Spearman against 0.30 without converting margins (shown for transparency only): C0 in all three cells.
- **Your open confirmation from v0.2:** the protocol reads C0 as "CI upper bound < 0.20" (the source says "C0 if < 0.20"). Every cell is C0 under either reading, so the confirmation no longer changes this decision.

## 3. Sensitivity (all τ-b; latent upper bound in brackets)

| Cell | M1, platform, by hours resident | M1, per-machine proxy | M1, all removals | M2, platform | M3, platform |
| --- | --- | --- | --- | --- | --- |
| a | −0.075 [−0.104] | −0.043 [−0.069] | −0.053 [−0.081] | 0.016 [0.026] | −0.001 [0.002] |
| b | −0.009 [−0.009] | 0.001 [0.017] | −0.020 [−0.035] | 0.002 [0.008] | 0.007 [0.021] |
| h | 0.042 [0.082] | −0.004 [0.000] | 0.013 [0.032] | 0.001 [0.039] | 0.011 [0.055] |

The full table, including the M2 and M3 rows for the other proxies, is `results/v2/trace_rho_table.csv`. The largest effect is cell a weighted by hours resident: high-tier work spends slightly more time on *safer* platforms (−0.075). That is the opposite of the direction in which budget-aware migration gains.

## 4. Dispersion: correlation near zero does not mean evenly spread

The Gini coefficient of the high-tier share across machines is 0.19-0.20 (a), 0.23-0.37 (b) and 0.14-0.25 (h) over the three windows. High-tier work is moderately clustered on some machines, but that clustering is not aligned with platform removal rates.

Platform rates of long removals range from 0.0001 to 0.016 per machine-day, a factor of about 100 between platforms. So the proxy does separate platforms; the null result is not a proxy with no spread.

**But the proxy rests on few events.** Before the last window, each cell has about 10,000 removals (10,190-11,372), of which only 79-166 are long: 111 (a), 79 (b) and 166 (h), over about 210,000 machine-days per cell. The platform ranking is therefore estimated from about 100 events per cell. The bootstrap over machines carries this uncertainty, and the all-removals variant (about 10,000 events) agrees, but a reviewer will ask; it goes in the paper's threats.

## 5. What C0 means for the project (PROTOCOL section 7)

- **Paper shape: measurement + safe policy + benchmark.** Real placement, as measured here, sits far below the correlation at which ranking by cost density gains over ranking by risk. The measurement is itself a headline result: critical work in Borg is neither protected onto low-risk platforms nor concentrated on risky ones. Rather than a "BAM pays off" claim, the paper's method claim is the safe guard P6, which must not lose to the tuned threshold, including on a pure-noise control.
- **The regimes keep their roles.** A, C and E remain the synthetic and adversarial evidence. B1 (ρ at this measurement) and B2 (tier given host class) become the realistic cells, near ρ = 0, and are run as planned.
- **Week 14 pilot cross-check.** At ρ = 0 the cost-tuned threshold P2c barely migrates, and P3 is within 2% of it. That is consistent with a realistic regime where little is gained.
- **Claim 1 of `FALSIFICATION.md`** ("real placement is at or above the break-even") is falsified for Google 2019 under every proxy and mapping. The protocol also requires the second source before declaring it falsified overall.

## 6. Threats (from `rho_definition.md`) and what this run did about them

| Threat | Status |
| --- | --- |
| Removals are not failures | Primary proxy uses long removals only; the all-removals variant agrees (magnitudes ≤ 0.053) |
| Platform mix confounds age | Within-platform τ-b with the per-machine proxy, combined over platforms by placements (`scripts/v2/13b_trace_strata.py`, `results/v2/trace_strata.json`): a 0.011 [0.009, 0.013], b −0.003 [−0.007, 0.002], h −0.005 [−0.010, −0.001]. Negligible inside platforms too, so platform mix does not hide a correlation |
| Scheduler policy | This is what we measure: where Borg runs critical work. It may not carry over to a scheduler without Borg's eviction protection |
| Short trace (31 days) | The platform proxy is primary; the per-machine proxy is shrunk to its platform |
| Dedicated machines | Excluded. Cell h has 5.4 million dedicated schedules hidden from the measurement; if those carry high-tier work on special hardware, cell h understates any correlation. To mention in the paper |
| Cells differ | Per-cell results and majority rule: all three agree |

## 7. Engineering notes (not results)

- The first aggregation attempts stalled at 0% CPU inside DuckDB 1.5.6, on a per-bucket query whose CTE was shared by a UNION ALL of the three windows. Each window now runs as its own query.
- The analysis crashed when the per-machine proxy had different risk levels per window; those curves are now computed per window and averaged.
- `lead()` now has a full tie-break. Before that, the group counts varied slightly between runs; the reported numbers are from the deterministic version.

## 8. Open before sign-off

1. Done 4 Oct: within-platform τ-b and removal counts (sections 4 and 6).
2. **The second placement source** (Alibaba 2018 or the tier mix) is needed before claim 1 is called falsified overall, not before G1 is signed off.
3. **Your sign-off.** After it, the class is final: record it in `LOG.md` and tag (suggested: `g1-c0`).

Signed off: ______  Date: ______
