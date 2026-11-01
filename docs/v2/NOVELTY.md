# Novelty over the base papers

Base papers (owner, 1 Nov 2026): Narya (Levy et al., OSDI 2020), NENYA (Wang et al., KDD 2022), Deoxys (Zhang et al., SoCC 2024). Sources: `reading/levy2020narya.md`, `reading/wang2022nenya.md`, `reading/zhang2024deoxys.md`, `T5_positioning.md`. NENYA read in full on 1 Nov 2026 (`reading/wang2022nenya.md`). Status of every claim below is as of 1 Nov 2026, before G3.

## The gap

All three learn which mitigation to take, at one operator, on private data, and report relative or normalised numbers. None of them asks when workload-aware ranking pays off, or compares against a probability threshold tuned to the same budget.

## Comparison

| | Narya | NENYA | Deoxys | This work |
| --- | --- | --- | --- | --- |
| Question | Which action for a flagged node? | Which action, trading mitigation cost against failures? | Reboot or Redeploy after a node is unhealthy? | When does cost-aware ranking pay off at all? |
| Timing and unit | Before failure; node and prediction rule | Before failure; database copy, hourly | After failure; node, per event | Before failure; VM |
| Method | A/B tests, Thompson sampling | Cascade reinforcement learning (cost fixed per action type) | Double ML, causal forest | Density ranking (not new), analysed in closed form |
| Per-instance criticality | No | No | No (VM count and types only) | Yes |
| Resource budget in GB | No (rate limits, caps) | No | No (capacity via an override threshold) | Yes, shared by all moves |
| Theory of when it pays | No | No | No | Yes (`THEORY.md` T1-T4) |
| Comparator | Fixed action plan | Random, reactive rules, Narya, SAC, DDPG | Random, legacy, Narya, NENYA, other estimators | Tuned threshold and never migrating, paired seeds, pre-registered bar |
| Data | Private | Private (Microsoft 365) | Private | Public (Backblaze, Google 2019) |
| Open artifact | None found | None found | None | Yes (VMMBench; DOI pending) |

## Claims

| # | Claim | Over the base papers | Evidence | Status |
| --- | --- | --- | --- | --- |
| N1 | Criticality and machine risk are essentially uncorrelated in public placement traces | None of the read papers measures this | `G1_decision.md`; \|τ-b\| ≤ 0.075 in three Google 2019 cells; cell f about zero, separate | **Holds.** Say "to our knowledge" until the literature sweep |
| N2 | The advantage of ranking is driven by cost spread, not a break-even correlation | None of the read papers has a theory of when ranking pays | `THEORY.md`; 3,024 / 3,024 points | **Holds** for the theory; the check is closed form against Monte Carlo |
| N3 | An open benchmark: public-data failure worlds, shared GB budget, paired seeds, frozen protocol | All three are private and not rerunnable | `vmmbench/`, `PROTOCOL.md`, `make reproduce-small` | **Holds** as built; v0.9 tag and DOI not yet done |
| N4 | Where new VMs go matters more than which VMs move | Narya has Avoid as one action among several; this isolates and measures it openly | ADR-011, `avoid_confirm.json`: seeds 2001-2050, B1 and B2, 6 of 6 comparisons pass; first found on eval seeds (`RESULTS_AVOID.md`) | **Confirmed under ADR-011, post-freeze, oracle predictor.** Weakens with noise: +3.8% in B1 at σ = 1. A and E evidence stays exploratory |
| N5 | A threshold tuned to the budget can do worse than never migrating | Not compared in the base papers | `RESULTS_W18.md` | **A and E only.** Needs B/C; must not read as a weak baseline |

## Not claims

- BAM as a new algorithm: it is Dantzig plus Elkan.
- Cost awareness as such: NENYA and Deoxys already have it.
- Beating Narya, NENYA or Deoxys: they are production systems, and P5 is only Narya-inspired.
- The P6 guard as a success: below never migrating in Week 18, and Deoxys has a per-event fallback precedent.
- Measured migration costs: assumed until Weeks 41-46.

## One sentence

> Production systems such as Narya, NENYA and Deoxys learn which mitigation to take, on private data; we ask the question they leave open, when workload-aware ranking pays off at all, and on public data we measure the condition, derive it in closed form and release a benchmark anyone can rerun.

The paper's own positioning sentence is still chosen at G3 (`POSITIONING.md`).

## Before relying on this

- [ ] Narya numbers against the OSDI text before quoting them (notes are from the technical report).
- [ ] Literature sweep for N1 and N3 ("first", "no existing benchmark").
- [ ] Re-read N5 at G3.
