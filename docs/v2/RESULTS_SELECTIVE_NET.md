# Destination-aware BAM and selective avoidance (ADR-013, post-freeze)

Run 2 Nov 2026 on seeds 4001-4050 (`scripts/v2/54_selective_net.py`, `logs/w_sel/run.log`): B1 and B2, 2% budget argument, oracle predictor, n = 50, paired by seed. 95% BCa; one-sided Wilcoxon with Holm within family. Rule SHA-256 `68ef8b4b…7c0`, stored with the results and matching the ADR file now. The ADR was frozen before the run but not committed to git first, so this is weaker evidence of order than ADR-011. Summary: `results/summary/selective_net.json`.

**Verdicts by the written rule: Family N confirmed (16 of 16 tests). Family S confirmed (8 of 8).**

Run on a scratch copy of the engine with the hook, while Week 30 needed the repo engine unchanged; the hook was then merged. Two rows rerun on the merged engine match exactly (B1 P0+selective, B2 P4-net, seed 4001; `results/summary/remigration_check.json`), and B1 seed 101 still gives P0 33,289 and P0+avoid 29,034.

## Family N: P4-net against never migrating and against P4

% saving against P0, mean [95% BCa].

| Setting | B1 P4 | B1 P4-net | B2 P4 | B2 P4-net | P4-net − P4, B1 / B2 |
| --- | --- | --- | --- | --- | --- |
| Default (N3) | +3.8 | **+4.6** [+4.0, +5.3] | +5.0 | **+5.9** [+5.4, +6.3] | +0.85 [+0.34, +1.36] / +0.87 [+0.66, +1.10] |
| G0-low, cheap migration (N2) | −17.1 | **+8.1** [+7.3, +8.8] | −15.2 | **+9.1** [+8.6, +9.6] | +25.2 / +24.3 |
| `level`, weights 1, 2, 3.33 (N2) | −77.8 | **+9.6** [+8.9, +10.3] | −77.5 | **+10.8** [+10.2, +11.3] | +87.4 / +88.3 |
| `steep`, weights 1, 3, 10 (N2) | −100.9 | **+15.4** [+14.5, +16.2] | −104.5 | **+15.7** [+15.0, +16.4] | +116.3 / +120.2 |

Migrations per run, B1: default 25,661 → 15,633; G0-low 288,975 → 28,059; `level` 731,334 → 39,566; `steep` 1,148,469 → 62,574.

Secondary, reported as they came out:

| | B1 P4 | B1 P4-net | B2 P4 | B2 P4-net |
| --- | --- | --- | --- | --- |
| G0-high | +0.8 [+0.2, +1.4] | +0.4 [−0.1, +0.9] | +0.9 [+0.5, +1.1] | +0.6 [+0.3, +0.9] |
| Noise σ = 0.5 | −4.8 | +1.5 [+0.8, +2.2] | −2.6 | +2.9 [+2.4, +3.4] |
| Noise σ = 1 | −30.5 | **−18.4** [−19.4, −17.5] | −25.5 | **−14.8** [−15.5, −14.2] |

**P4-net does not fix noise.** It stays well below never migrating at σ = 1. At G0-high it adds nothing and in B1 its interval includes zero.

## Family S: selective avoidance, no migration

Closed shares: low 2%, medium 5%, high 10%; comparators close 4.4% for all tiers.

| | B1 saving | B1 rejected arrivals | B2 saving | B2 rejected arrivals |
| --- | --- | --- | --- | --- |
| P0 | 0 | 169.1 | 0 | 1.5 |
| P0+avoid(W), today's whole-host mark | +16.9 [+16.2, +17.6] | 279.9 | +15.8 [+15.1, +16.4] | 14.6 |
| redirect(W), same mechanism, no tiers | +17.0 [+16.1, +17.8] | 250.1 | +16.8 [+16.2, +17.4] | 11.0 |
| **P0+selective** | **+17.5** [+16.7, +18.1] | **66.4** | **+17.5** [+16.9, +18.1] | **0.4** |

Paired differences of P0+selective: saving against P0+avoid(W) B1 +0.58 [0.00, +1.17], B2 +1.71 [+1.27, +2.18]; against redirect(W) B1 +0.45 [−0.25, +1.16], B2 +0.67 [+0.33, +1.03]. Rejected arrivals against P0+avoid(W) B1 −213 [−220, −207], B2 −14 [−17, −12]; against redirect(W) B1 −184 [−190, −177], B2 −11 [−12, −9].

**What this shows: the same saving with far fewer rejected VMs.** It does not show a much larger saving: the gain in saving is under 2 points, and in B1 it cannot be told from zero against redirect(W). The test S1 is non-inferiority, and that is all that was asked of it.

Secondary, noise:

| | B1 selective | B1 avoid(W) | B1 redirect(W) | B2 selective | B2 avoid(W) | B2 redirect(W) |
| --- | --- | --- | --- | --- | --- | --- |
| σ = 0.5 | +15.0 | +14.5 | +14.8 | +15.1 | +12.0 | +14.5 |
| σ = 1 | **+10.3** | +8.0 | +8.4 | **+10.0** | +5.3 | +8.4 |

Against P4 at σ = 1, selective is ahead by about 40 points in B1 and 35 in B2. The whole class of placement policies stays above zero at every noise level run.

**Combined P4-net + selective:** B1 +17.4 [+16.6, +18.2], 588 migrations; B2 +17.5 [+16.9, +18.1], 552. That is the same as selective alone. **With selective placement, migration adds nothing measurable here**, and the policy itself finds almost nothing worth moving.

**Extended law:** S = φ Σ a_t R(q_t), φ and R frozen in ADR-012. Predicted against observed: B1 19.2 against 17.5; B2 15.3 against 17.5. Errors of 1.7 and 2.1 points, in opposite directions. Observed B1 and B2 are equal here, while φ differs by regime, so φ does not carry over cleanly to tiered closure. Two points are not a test; this is not a confirmation.

## Why BAM collapses (dev seeds only, no verdict)

`scripts/v2/55_remigration_check.py`, seeds 101-105. P4-once is BAM that may move a VM only once: it tests the cause ADR-013 proposed.

| Setting, B1 | P4 | P4-once | P4-net | Most moves of one VM, P4 / P4-net |
| --- | --- | --- | --- | --- |
| Default | +5.4 | +5.8 | +5.5 | 7.6 / 2.0 |
| G0-low | −15.8 | +3.2 | **+10.0** | 14 / 3.2 |
| `level` | −75.6 | −2.6 | **+10.6** | 14 / 3.0 |

B2 follows the same shape: G0-low −14.3, +4.9, +9.9; `level` −78.2, 0.0, +11.3.

**Re-migration explains most of the collapse, not all of it.** Banning a second move recovers most of the loss. It still leaves P4 7 to 13 points below P4-net at the same settings, with about four times as many migrations (B1 G0-low 114,789 against 28,497). So first moves that are not worth it also cost a lot: `b` treats the destination as safe when it is not. Five dev seeds, descriptive.

## Limits

- Simulation only, oracle hazards in both primary families. Costs are assumed; G0-low and G0-high are joint extremes of published measurements.
- Only the seeds are blind. All comparators were seen on dev seeds and q was picked from a dev-seed grid.
- Rejected arrivals are a small absolute quantity: about 0.03% of arrivals at most in B1 (280 of about 878,000), and few in B2 at any setting. Selective rejects fewer than P0 itself (66 against 169), which closing hosts should not do by itself. The mechanism is not shown, and it may come from rank-based placement spreading load.
- Noise here is ADR-012's: one draw per host per 30-day block (`54_selective_net.py`). ADR-011 redraws daily (`vmsim/predictor.py`), which is much harsher: B1 P4 at σ = 1 is −30.5 here and −248 in `avoid_confirm.json`. The two are not comparable, and P4-net and P0+selective were not run under daily noise.
- P4-net does not make BAM robust. It removes one specific failure: collapse under cheap migration or high cost level, at a correct predictor.
- `p_dst` here uses the mean over up hosts of the engine's destination rule; a real allocator's rule would differ.
