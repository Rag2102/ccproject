# Why does P5 beat BAM? (exploratory diagnosis, post-freeze)

Asked by the Week 18 result (`RESULTS_W18.md`): against never migrating, the Narya-inspired P5 saves more than BAM in every A and E cell, with about 34× fewer migrations.

**Setup:**
- Code: `scripts/v2/36_diag_p5_vs_bam.py`; variants in `vmsim/policies/variants.py`, tests in `tests/v2/test_vmsim_variants.py`. Data: `results/v2/diag_p5_vs_bam.json`.
- Run conditions: dev seeds 101-105 (never the evaluation seeds), the frozen matrix's scale (2,000 hosts × 365 days), oracle predictor, 2% budget, regimes A1, A3, A7, E1, E3. The run took 99 s on 4 cores.
- Status: exploratory and post-freeze. Logged in `CHANGES_AFTER_FREEZE.md`; outside the confirmatory family.

## Two hypotheses were tested

1. **Avoid-allocation.** P5 can mark a flagged host so it takes no new VMs, an action no other policy has (`narya.py`: `avoid()`; `base.py`: "Only P5 uses it").
2. **The option to wait.** BAM judges each move over the 30-day horizon, although it decides again every day.

## Result (mean saving against never migrating; range over 5 seeds)

| Policy | A1 | A3 | A7 | E1 | E3 | Migrations (A1) |
| --- | --- | --- | --- | --- | --- | --- |
| P4 BAM | +4.5 | +11.9 | +8.6 | −1.8 | +4.9 | 23,539 |
| P5 Narya-inspired | +8.0 | +16.3 | +17.7 | +7.1 | +8.4 | 580 |
| **P5 with avoid off** | **−0.8** | **+3.7** | **+3.4** | **−0.7** | **−0.8** | 1,156 |
| **P0 + avoid (no migration)** | **+10.6** | **+19.6** | **+21.9** | **+10.7** | **+10.6** | 0 |
| P4 + avoid | +11.1 | +20.7 | +20.5 | +10.2 | +11.7 | 14,313 |
| P4-wait7 | +2.7 | +7.6 | +6.4 | +0.2 | +1.8 | 1,541 |
| P4-wait1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 |
| P6 with a P0 fallback | +3.2 | +9.4 | +6.4 | −1.7 | +3.9 | 18,087 |

## What it shows

1. **P5's whole advantage is avoid-allocation.** With its marks switched off, P5 is at or below BAM in every regime (−0.8% to +3.7%).
2. **Avoid-allocation alone beats every migration policy in the study.** Marking the riskiest 2% of hosts each day so they take no new VMs saves 10.6-21.9% against never migrating, with no migrations and no budget. Rejected arrivals barely change (A1: 3 → 4 per run; A3: 148 → 159).
3. **Migration adds little on top of avoidance.** BAM + avoid is within about ±1.4 points of avoidance alone.
4. **The option-to-wait hypothesis is wrong.** BAM with a 7-day window migrates 15× less but saves *less* than BAM (A1: +2.7% against +4.5%). With a 1-day window it never migrates. BAM's many low-hit-rate migrations do pay for themselves, narrowly.
5. **The guard with a P0 fallback is no longer harmful in A** (+3.2% to +9.4%), but stays below BAM and slightly below zero in E1.

**Mechanism** (A1, seed 101, cost split by component):

| Policy | Long-lived interruptions | Short-lived interruptions | Migration | Total |
| --- | --- | --- | --- | --- |
| P0 | 31,328 | 1,353 | 0 | 32,681 |
| P4 BAM | 27,295 | 1,353 | 2,466 | 31,114 |
| P0 + avoid | 27,503 | 1,353 | 0 | 28,856 |

Avoidance protects long-lived VMs about as much as BAM's migrations do, but at placement time, for free. BAM pays most of its gross benefit back in migration cost. The short-lived VMs' cost is identical under every policy, by design (SIM_SPEC: charged at each failure as a Poisson draw).

## What this means (for G3 and the paper; not decided here)

- **The comparison the protocol registered is between ranking rules for migration, but the largest lever in this simulator is not migration at all.** Placement-time avoidance of risky hosts dominates, and it is the cheaper half of what Narya actually does.
- **A fair comparison needs avoidance as a baseline.** "P0 + avoid" should sit beside P2 and P0 in every results table, and the B/C runs should include it. That would be an exploratory addition (proposed in ADR-010).
- **Caveats** that keep this exploratory:
  - five dev seeds;
  - oracle probabilities (avoidance with a noisy predictor is untested);
  - the simulator charges no capacity cost for avoided hosts beyond rejected arrivals;
  - 2% marking share only;
  - marked hosts keep their resident VMs, so the effect builds up as VMs turn over.
- **The paper's possible shape:** "Which VMs to move matters less than where new VMs go." The theory (spread of cost per GB drives the migration advantage) and the measurement (ρ ≈ 0) still stand; the policy contribution changes.
