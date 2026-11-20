# Week 18 results: regimes A and E (read 5 Oct 2026, before B and C exist)

Run: `run_w18.sh`, commit 3153b94; tuning 02:56-06:16, runs to 10:33, collect 10:33 (330 of 330 cells, no runs missing). About 95 minutes were lost to sleep. Statistics: `30_stats.py --groups A E`, `34_vs_p0.py --groups A E`; figures F4 (`31_fig_f4.py`) and F4b (`35_fig_vs_p0.py`, new, the ADR-005 companion). Protocol order (section 9): this note and the A/E paragraph are written before B and C are run or opened.

## The pre-registered criterion

- **All 12 confirmatory comparisons in A3 and A5 meet the bar** (adjusted Δ ≥ 1%, Holm p < 0.05). The family's Holm scope is partial (12 of 30) until B and C exist.
- **The ADR-007 SD extension is triggered.** SD(Δ) is above 1.6% for P5 and P6 in A3 and A5: 1.6-2.4% for P5 and 7.1-9.8% for P6. Under the pre-registered rule, A3 and A5 extend to n = 50 (seeds 31-50) for every policy and are decided against 2.1%. That run is queued in `run_rest.sh`, after the second source. The trigger depends on the SD only; with Δ at +41% to +74%, the extension will not change the verdicts, but the rule is applied anyway.

## What the criterion hides: P2 costs more than doing nothing

The budget-tuned threshold P2 is worse than never migrating (P0) **in every seed of every A and E cell**:
- −29% to −60% at a 0.5% budget;
- −80% to −132% at 1%;
- −189% to −285% at 2%;
- −535% to −772% at 5%.

Spending the budget forces it to move VMs whose expected benefit is negative. ADR-005 anticipated this, so "beats P2 by ≥ 1%" is nearly guaranteed for any policy that can decline to migrate. The meaningful comparison is against P0 (Table 3's new columns, F4b).

## Against never migrating (F4b; % saving, 95% BCa, 2% budget)

| Regime | ρ_L / σ_κ | P3 v1 rule | **P4 BAM** | P5 Narya-inspired | P6 guard | P2 |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | 0 | +1.7 | **+5.0** [+4.4, +5.6] | +8.6 [+7.8, +9.3] | −49.7 | −281 |
| A3 | 0.3 | +6.7 | **+10.8** [+9.4, +12.0] | +15.5 [+14.2, +16.6] | −33.1 | −219 |
| A5 | 0.6 | +4.8 | **+9.2** [+7.7, +10.6] | +15.5 [+13.9, +17.0] | −30.8 | −202 |
| A7 | 0.9 | +3.1 | **+7.5** [+6.0, +8.9] | +16.9 [+15.4, +18.3] | −29.9 | −189 |
| E1 | σ 0.25 | −2.3 | **−2.4** [−3.1, −1.7] | +8.4 | −46.8 | −237 |
| E2 | σ 0.5 | +0.4 | **+1.6** [+1.1, +2.1] | +8.1 | −51.1 | −274 |
| E3 | σ 1.0 | +1.7 | **+5.3** [+4.8, +5.9] | +8.6 | −50.6 | −285 |

1. **BAM beats doing nothing** in every A regime (93-100% of seeds), by 5% at ρ_L = 0 and up to 11% at ρ_L = 0.3. The curve is hump-shaped in ρ_L, not monotone.
2. **Spread drives it at ρ = 0, as T3 says.** At zero correlation BAM goes from −2.4% to +1.6% to +5.3% as σ_κ goes from 0.25 to 0.5 to 1.0. With little cost spread, BAM is slightly worse than doing nothing. This is the first simulation evidence for C2b's direction.
3. **The budget never binds.** BAM uses 8.9% of the smallest (0.5%) budget, and its saving is identical at every budget. Budget-aware *ranking* therefore plays no role here; BAM's gain is its stopping rule (b > 0). The paper's framing has to say this.
4. **The Narya-inspired bandit (P5) beats BAM everywhere.** In every A and E cell its interval lies entirely above BAM's, with about 34× fewer migrations (699 against 23,827 at A1, 2%). Diagnosed afterwards (`DIAG_P5_VS_BAM.md`): the reason is not the option to wait, which was tested and refuted, but P5's avoid-allocation action. With it switched off P5 is no better than BAM, and avoidance alone beats every migration policy. P5 also uses the oracle probabilities here.
5. **The guard (P6) is worse than never migrating** in most cells, because its fallback is P2 (owner decision, 4 Oct: the fallback stays P2 as pre-registered). It does better than P2, but it cannot be recommended as specified.
6. **Theory vs simulation (F4).** T3 with measured parameters gets the direction right (Δ against P2 falls with ρ_L and rises with the budget) but under-predicts the level, by 7-24 points. That is expected: the budget does not bind and the stopping term dominates.

## What this means (for the G3 discussion with your advisor; not decided here)

- The pre-registered win is real but uninformative, for the reason ADR-005 recorded. The paper must lead with the comparison against P0, as the abstract's macro sentences already allow.
- The paper's primary method is beaten by a baseline. That is a result, and the protocol says it goes in unchanged. Two honest framings, to choose after B/C:
  - (a) "Cost-aware stopping matters more than budget-aware ranking; a learning policy that waits does better still."
  - (b) "Workload-aware migration helps only when costs per GB are spread, and an adaptive baseline captures most of it."
- Candidate post-freeze work (exploratory, Phase 6): a BAM variant that accounts for the option to wait (for example, b computed on the residual horizon or a deferral threshold), and the guard with P0, not P2, as its fallback. Both would be new, labelled exploratory, and outside the 30-comparison family.

## Not yet known

- B1/B2/C (the measured-correlation and realistic regimes): Week 19, in `run_rest.sh`.
- The D adaptive regime and the guard's H4 targets: Week 21.
- Robustness, Morris and the noisy predictor: Week 20.
- Replication on seeds 1001-1030.
