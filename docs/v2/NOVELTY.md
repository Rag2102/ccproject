# Novelty over the base papers

Base papers (owner, 1 Nov 2026): Narya (Levy et al., OSDI 2020), NENYA (Wang et al., KDD 2022), Deoxys (Zhang et al., SoCC 2024). Sources: `reading/levy2020narya.md`, `reading/wang2022nenya.md`, `reading/zhang2024deoxys.md`, `T5_positioning.md`. NENYA read in full on 1 Nov 2026 (`reading/wang2022nenya.md`). Status of every claim below is as of 2 Nov 2026, before G3. N6-N8 are post-freeze, outside the 30-comparison family and outside G3.

## The gap

All three learn which mitigation to take, at one operator, on private data, and report relative or normalised numbers. None of them asks when workload-aware ranking pays off, or compares against a probability threshold tuned to the same budget.

## Comparison

| | Narya | NENYA | Deoxys | This work |
| --- | --- | --- | --- | --- |
| Question | Which action for a flagged node? | Which action, trading mitigation cost against failures? | Reboot or Redeploy after a node is unhealthy? | When does cost-aware ranking pay off at all? |
| Timing and unit | Before failure; node and prediction rule | Before failure; database copy, hourly | After failure; node, per event | Before failure; VM |
| Method | A/B tests, Thompson sampling | Cascade reinforcement learning (cost fixed per action type) | Double ML, causal forest | Density ranking (not new), analysed in closed form |
| Per-instance criticality | No | No | Node-level only (VM count and types, whether important workloads are on the node) | Yes, per VM |
| Resource budget in GB | No (rate limits, caps) | No | No (capacity via an override threshold) | Yes, shared by all moves |
| Theory of when it pays | No | No | No | Yes (`THEORY.md` T1-T4) |
| Comparator | Fixed action plan | Random, reactive rules, Narya, SAC, DDPG | Random, legacy, Narya, NENYA, other estimators | Tuned threshold and never migrating, paired seeds, pre-registered bar |
| Data | Private | Private (Microsoft 365) | Private | Public (Backblaze, Google 2019) |
| Open artifact | None found | None found | None | Yes (VMMBench; DOI pending) |

## Claims

| # | Claim | Over the base papers | Evidence | Status |
| --- | --- | --- | --- | --- |
| N1 | Criticality and machine risk are essentially uncorrelated in public placement traces | None of the read papers measures this | `G1_decision.md`; \|τ-b\| ≤ 0.075 in three Google 2019 cells; cell f about zero, separate | **Holds.** Say "to our knowledge" (`LIT_SWEEP.md`) |
| N2 | The advantage of ranking is driven by cost spread, not a break-even correlation | None of the read papers has a theory of when ranking pays | `THEORY.md`; 3,024 / 3,024 points | **Holds** for the theory; the check is closed form against Monte Carlo |
| N3 | An open benchmark: public-data failure worlds, shared GB budget, paired seeds, frozen protocol | All three are private and not rerunnable | `vmmbench/`, `PROTOCOL.md`, `make reproduce-small` | **Holds** as built; v0.9 tag and DOI not yet done |
| N4 | Where new VMs go matters more than which VMs move | Narya has Avoid as one action among several; this isolates and measures it openly | ADR-011, `avoid_confirm.json`: seeds 2001-2050, B1 and B2, 6 of 6 comparisons pass; first found on eval seeds (`RESULTS_AVOID.md`) | **Confirmed under ADR-011, post-freeze, oracle predictor.** Weakens with noise, and stays positive: B1 at σ = 1 is +5.9% under ADR-012, against BAM −30.2%. A and E evidence stays exploratory |
| N5 | A threshold tuned to the budget can do worse than never migrating | Not compared in the base papers | `RESULTS_W18.md` | **Holds in A, E, B and C:** B1 at 2% −273% (`vs_p0.json`, n = 50), and across the published cost range (`RESULTS_COSTRANGE.md`). P2 spends its budget even when moving does not pay, so it must not read as a beaten baseline: say what it shows, that matching a budget is not a reason to spend it |
| N6 | The saving from avoidance follows a concentration law, S = φ R(q, σ), predictable before running the simulator | None of the base papers gives avoidance a law; Narya measures Avoid only as one action | ADR-012, `avoid_law.json`: 19 out-of-sample cells on seeds 3001-3050, Spearman 0.98 (B1), 0.97 (B2), mean error 1.2 and 0.9 points | **Supported under ADR-012,** simulation only. φ is fitted, so this is a regularity with one fitted constant, not a derivation |
| N7 | Charging destination risk stops BAM collapsing when migration is cheap or failure cost is high | Narya counts interruptions on receiving nodes in its outcome, but no per-VM decision in the three papers charges it | ADR-013, `selective_net.json`: seeds 4001-4050, 16 of 16 tests. B1 G0-low −17.1 to +8.1, `level` −77.8 to +9.6, `steep` −100.9 to +15.4; default +0.85 point | **Confirmed under ADR-013,** oracle. Does **not** fix noise: B1 σ = 1 still −18.4. Adds nothing at G0-high. Cause on dev seeds: mostly re-migration, partly first moves. A patent ([US 9277002](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9277002)) has a post-migration failure term; not read in full, so never say "first" |
| N8 | Closing risky hosts per tier gives the same saving as closing them to everyone, with far fewer rejected VMs and more resistance to noise | Narya's Avoid and these comparators close a node to all VMs; none of the three has per-VM criticality to tier by | ADR-013: 8 of 8 tests. Rejected arrivals B1 66 against 280, B2 0.4 against 14.6; saving +17.5 against +16.9 and +15.8; σ = 1 +10.3 against +8.0, +10.0 against +5.3 | **Confirmed under ADR-013,** oracle. Rejections are a small absolute number; mechanism not shown; the saving gain is under 2 points. Adding migration on top adds nothing measurable (+17.4) |

## Limits that must be said with these

- **BAM's saving against never migrating depends on the assumed cost.** At the two ends of the published range: −17% (cheap) and about +1% (expensive) in B1 (`RESULTS_COSTRANGE.md`). Its win over P2 holds across the range.
- All of this is simulation with assumed tier weights. Oracle predictor unless a noise level is stated.
- N4, N6, N7 and N8 are post-freeze. For N6 to N8 only the seeds are blind, since the policies and settings came from dev seeds. ADR-012 and ADR-013 record order by a stored hash, not a prior commit, unlike ADR-011.

## Not claims

- BAM as a new algorithm: it is Dantzig plus Elkan.
- Cost awareness as such: NENYA and Deoxys already have it.
- Beating Narya, NENYA or Deoxys: they are production systems, and P5 is only Narya-inspired.
- The P6 guard as a success: below never migrating in Week 18, and Deoxys has a per-event fallback precedent.
- Measured migration costs: assumed until Weeks 41-46. The published range brackets them; it does not measure them.
- That P4-net makes BAM robust: it stays negative under noise.

## One sentence

> Production systems such as Narya, NENYA and Deoxys learn which mitigation to take, on private data; we ask the question they leave open, when workload-aware ranking pays off at all, and on public data we measure the condition, derive it in closed form and release a benchmark anyone can rerun.

The paper's own positioning sentence is still chosen at G3 (`POSITIONING.md`).

## Before relying on this

- [ ] Narya numbers against the OSDI text before quoting them (notes are from the technical report).
- [x] Literature sweep for N1 and N3: `LIT_SWEEP.md`. Holds as "to our knowledge"; no "first".
- [ ] N7 and N8: three searches only (`LIT_SWEEP.md`). Claim them over the base papers, not over all prior work. Read US 9277002 in full before the paper.
- [ ] Re-read N5 at G3.
