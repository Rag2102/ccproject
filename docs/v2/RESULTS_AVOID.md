# Avoidance on the evaluation seeds (ADR-010, exploratory, post-freeze)

Run 26 Oct 2026, 22:06-22:20 (`37_explore_avoid.py`, `logs/explore_avoid.log`): P0+avoid and P4+avoid on every regime of groups A-E, eval seeds 1-30, the frozen matrix's scale and predictor pairing; 1,440 runs in 14 minutes. Summary: `results/summary/explore_avoid.json` (per-run rows in `results/explore/avoid/`). Outside the confirmatory family and the G3 rule (ADR-010). B, C and D are run but not yet summarised: they have no P0 runs until Week 19 (`run_rest.sh` re-summarises at the end).

**The dev-seed finding holds on the 30 evaluation seeds** (`DIAG_P5_VS_BAM.md` had 5 dev seeds).

## Saving against never migrating (% , mean [95% BCa], 2% budget)

| Regime | P0+avoid (no migration) | P4+avoid | P4 BAM | P5 Narya-inspired |
| --- | --- | --- | --- | --- |
| A1 (ρ_L 0) | **+11.0** [+10.4, +11.7] | +11.8 [+11.1, +12.5] | +5.0 [+4.4, +5.6] | +8.6 [+7.8, +9.3] |
| A2 | **+15.6** [+14.7, +16.7] | +17.4 [+16.3, +18.7] | +9.7 [+8.7, +10.9] | +12.9 [+11.7, +14.3] |
| A3 | **+17.8** [+16.8, +18.9] | +18.7 [+17.4, +19.9] | +10.8 [+9.4, +12.0] | +15.5 [+14.2, +16.6] |
| A4 | **+18.7** [+17.4, +20.1] | +19.4 [+18.1, +20.8] | +10.4 [+8.7, +11.8] | +15.8 [+14.5, +17.0] |
| A5 | **+18.5** [+17.3, +19.7] | +18.9 [+17.6, +20.2] | +9.2 [+7.7, +10.6] | +15.5 [+13.9, +17.0] |
| A6 | **+19.1** [+17.9, +20.3] | +19.3 [+17.8, +20.6] | +8.3 [+6.7, +9.8] | +16.0 [+14.7, +17.5] |
| A7 (ρ_L 0.9) | **+19.7** [+18.6, +21.0] | +19.3 [+17.9, +20.5] | +7.5 [+6.0, +8.9] | +16.9 [+15.4, +18.3] |
| E1 (σ 0.25) | **+10.6** [+9.9, +11.4] | +10.2 [+9.5, +11.0] | −2.4 [−3.1, −1.7] | +8.4 [+7.5, +9.3] |
| E2 (σ 0.5) | **+10.9** [+10.3, +11.6] | +11.0 [+10.3, +11.8] | +1.6 [+1.1, +2.1] | +8.1 [+7.2, +8.9] |
| E3 (σ 1.0) | **+11.0** [+10.4, +11.7] | +11.7 [+11.1, +12.5] | +5.3 [+4.8, +5.9] | +8.6 [+7.8, +9.4] |

P0+avoid and P4+avoid beat never migrating in every seed of every cell (100%). P4+avoid gives the same result at 1% and 2%: the budget does not bind, as for BAM.

## What it shows

1. **Avoidance alone beats every migration policy in every A and E cell**, by 11-20% against never migrating, with no migrations and no budget. It beats BAM by 6-13 points and P5 by 2-3 points; its interval is clear of both in every cell.
2. **Migration adds at most about 2 points on top of avoidance** (P4+avoid against P0+avoid: −0.4 to +1.8), and costs 4,000-45,000 migrations per run for it. In A7 and E1 adding BAM is slightly worse than avoidance alone.
3. **Avoidance does not need cost spread.** It saves about 11% at every σ_κ in E, where BAM goes from −2.4% to +5.3%. Its gain grows with ρ_L (11% to 20%) and then flattens; BAM's is hump-shaped.
4. **Capacity cost is small but not zero.** Rejected arrivals per run rise from 2.2 to 3.1 at A1 and E, and by up to about a quarter where the fleet is tight (A3: 152 → 160; A5: 131 → 159; A7: 114 → 140; A2 unchanged). The simulator prices rejections only through the arrivals lost, not as a separate capacity cost; this is the main caveat.

## Caveats (unchanged from the diagnosis)

- Oracle probabilities. Avoidance with a noisy or drifting predictor is untested (D is run but awaits its P0 runs; a noisy-predictor run is a natural Week 20-style addition).
- One marking share (2%).
- Marked hosts keep their resident VMs, so the effect builds up as VMs turn over; a shorter horizon would show less.
- Exploratory and post-freeze: it informs G3's discussion and the paper's framing, not the confirmatory verdicts.
