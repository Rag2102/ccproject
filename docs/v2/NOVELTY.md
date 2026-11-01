# Novelty over the base papers

Base papers (owner, 1 Nov 2026): Narya (Levy et al., OSDI 2020), NENYA (Wang et al., KDD 2022), Deoxys (Zhang et al., SoCC 2024). Sources: `reading/levy2020narya.md`, `reading/zhang2024deoxys.md`, `T5_positioning.md`. **NENYA is abstract only**, so its "not stated" cells mean the abstract does not say; they are not evidence that the paper lacks the feature. Status of every claim below is as of 1 Nov 2026, before G3.

## The gap

All three learn which mitigation to take, at one operator, on private data, and report relative or normalised numbers. None of those that were read in full asks when workload-aware ranking pays off, or compares against a probability threshold tuned to the same budget.

## Comparison

| | Narya | NENYA (abstract only) | Deoxys | This work |
| --- | --- | --- | --- | --- |
| Question | Which action for a flagged node? | Which action, trading mitigation cost against failures? | Reboot or Redeploy after a node is unhealthy? | When does cost-aware ranking pay off at all? |
| Timing and unit | Before failure; node and prediction rule | Database (filter, then choose an action) | After failure; node, per event | Before failure; VM |
| Method | A/B tests, Thompson sampling | Cascade reinforcement learning | Double ML, causal forest | Density ranking (not new), analysed in closed form |
| Per-VM criticality | No | Not stated | No (VM count and types only) | Yes |
| Resource budget in GB | No (rate limits, caps) | Not stated | No (capacity via an override threshold) | Yes, shared by all moves |
| Theory of when it pays | No | Not stated | No | Yes (`THEORY.md` T1-T4) |
| Comparator | Fixed action plan | Not stated | Random, legacy, Narya, NENYA, other estimators | Tuned threshold and never migrating, paired seeds, pre-registered bar |
| Data | Private | Private (Microsoft 365) | Private | Public (Backblaze, Google 2019) |
| Open artifact | None found | Not stated | None | Yes (VMMBench; DOI pending) |

## Claims

| # | Claim | Over the base papers | Evidence | Status |
| --- | --- | --- | --- | --- |
| N1 | Criticality and machine risk are essentially uncorrelated in public placement traces | None of the read papers measures this | `G1_decision.md`; \|τ-b\| ≤ 0.075 in three Google 2019 cells; cell f about zero, separate | **Holds.** Say "to our knowledge" until the literature sweep |
| N2 | The advantage of ranking is driven by cost spread, not a break-even correlation | None of the read papers has a theory of when ranking pays | `THEORY.md`; 3,024 / 3,024 points | **Holds** for the theory; the check is closed form against Monte Carlo |
| N3 | An open benchmark: public-data failure worlds, shared GB budget, paired seeds, frozen protocol | All three are private and not rerunnable | `vmmbench/`, `PROTOCOL.md`, `make reproduce-small` | **Holds** as built; v0.9 tag and DOI not yet done |
| N4 | Where new VMs go matters more than which VMs move | Narya has Avoid as one action among several; this isolates and measures it openly | `RESULTS_AVOID.md`, ADR-010 | **Exploratory.** A and E shown; B, C and D not summarised. Report the rise in rejected arrivals |
| N5 | A threshold tuned to the budget can do worse than never migrating | Not compared in the base papers | `RESULTS_W18.md` | **A and E only.** Needs B/C; must not read as a weak baseline |

## Not claims

- BAM as a new algorithm: it is Dantzig plus Elkan.
- Beating Narya, NENYA or Deoxys: they are production systems, and P5 is only Narya-inspired.
- The P6 guard as a success: below never migrating in Week 18, and Deoxys has a per-event fallback precedent.
- Measured migration costs: assumed until Weeks 41-46.

## One sentence

> Production systems such as Narya, NENYA and Deoxys learn which mitigation to take, on private data; we ask the question they leave open, when workload-aware ranking pays off at all, and on public data we measure the condition, derive it in closed form and release a benchmark anyone can rerun.

The paper's own positioning sentence is still chosen at G3 (`POSITIONING.md`).

## Before relying on this

- [ ] NENYA in full (*yours*: ACM blocks automated access; save the PDF into the repo's `reading/` notes or send it).
- [ ] Narya numbers against the OSDI text before quoting them (notes are from the technical report).
- [ ] Literature sweep for N1 and N3 ("first", "no existing benchmark").
- [ ] Re-read N4 and N5 after the B/C statistics and G3.
