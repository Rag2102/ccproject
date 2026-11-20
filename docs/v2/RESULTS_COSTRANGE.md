# Migration-cost range (ADR-009, exploratory, post-freeze)

Run 2 Nov 2026, 03:10-04:55 (`run_w30.sh`, `logs/w30/`): B1, B2 and C at G0-low and G0-high; P0, P2, P4, P6; 1% and 2%; seeds 1-30; 0 missing. Outside the 30-comparison family. Settings derived by the rule in `configs/v2/cost_range.yaml`, written before any rerun, from 4 of the 6 sources (Clark 2005, Voorsluys 2009, Akoush 2010, Hu 2013). Liu 2011 and SoCC 2015 are not read: the ACM site returned a bot challenge. Summaries: `results/summary/S_costrange.json`, `vs_p0_costrange.json`.

| Setting | Usable share | Dirty rate at full CPU | Blackout |
| --- | --- | --- | --- |
| G0-low (each extreme, so cheaper than any one setup) | 0.77 | 2.3 MB/s | 0.06 s |
| Default (assumed, not rerun) | 0.50 | 150 MB/s | 1 s |
| G0-high (each extreme, so dearer than any one setup) | 0.10 | 200 MB/s | 3 s |

## Against never migrating (P0), % saving, mean [95% BCa], 2% budget

| Regime | P4 G0-low | P4 default (n = 50) | P4 G0-high | P2 G0-low | P2 G0-high | P6 G0-low | P6 G0-high |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B1 | −17.4 [−18.5, −16.1] | +4.0 | +1.0 [+0.3, +1.7] | −156.2 | −1708.3 | −44.0 | −325.0 |
| B2 | −15.7 [−17.1, −14.1] | +5.1 | +0.9 [+0.4, +1.2] | −161.4 | −1676.4 | −43.9 | −320.8 |
| C | −2.8 [−4.6, −0.9] | +4.6 | +0.1 [−0.7, +0.9] | −90.8 | −1458.0 | −20.4 | −288.2 |

P4's result at 1% is within 0.5 point of these in every cell, since it rarely reaches the budget at either end (at most 64% used).

## Against the tuned threshold (P2), % Δ, 2% budget

| Regime | P4 G0-low | P4 G0-high |
| --- | --- | --- |
| B1 | +54.2 [+53.8, +54.6] | +94.5 [+94.5, +94.6] |
| B2 | +55.7 [+55.3, +56.1] | +94.4 [+94.4, +94.5] |
| C | +46.1 [+45.6, +46.5] | +93.6 [+93.5, +93.6] |

At 1%, P4 G0-low: B1 +30.6, B2 +32.3, C +21.1. These cells have no Holm correction: they are exploratory.

## Reading

1. **The win over P2 survives the whole range.** ADR-009's condition (the result crosses the 1% bar) does not occur. That result is mostly P2 being bad: P2 spends its budget even when migration does not pay.
2. **The saving against P0 does not survive.** Default +4 to +5%. G0-high about +1% or less, because BAM nearly stops migrating (949 to 4,027 migrations per run), which is correct behaviour. **G0-low is negative in all three regimes**, with 290,000 to 356,000 migrations per run. This is the less intuitive way round: cheaper migration makes BAM worse. ADR-009 says this goes in the Evaluation section.
3. **So the headline is conditional on the assumed cost.** BAM's positive saving against never migrating holds at the assumed central setting, is near zero at the dear end, and reverses at the cheap end. A BAM saving against P0 must not be stated without this.
4. **The guard P6 does not help.** It is below P0 in all 12 cells (3 regimes, 2 ends, 1% and 2% budget).
5. **G0-low and G0-high are joint extremes.** Each combines the best or worst value from different papers, so no single measured system sits at either end. They bracket; they are not likely settings. Neither end says what a real deployment would see.

The cause of point 2 is examined in `RESULTS_SELECTIVE_NET.md`: mostly re-migration, partly first moves that ignore destination risk. P4-net removes the negative result at G0-low on fresh seeds (B1 +8.1, B2 +9.1).
