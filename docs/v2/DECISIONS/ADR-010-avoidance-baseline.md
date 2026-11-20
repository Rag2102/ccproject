# ADR-010: add placement-time avoidance as an exploratory baseline (proposed)
Status: **accepted** (owner, 13 Oct 2026; drafted after the post-freeze diagnosis `DIAG_P5_VS_BAM.md`)
Date: 2026-10-13

Context. The Week 18 run found the Narya-inspired P5 ahead of BAM against never migrating. On dev seeds, the diagnosis traced all of P5's advantage to avoid-allocation (marking risky hosts so they take no new VMs), an action no other policy has. Avoidance alone, with no migration, saved 10.6-21.9% against never migrating, more than any migration policy, and BAM added at most about one point on top of it. The frozen matrix has no avoidance-only baseline, so the reader cannot see this.

Decision (proposed):
- Add two exploratory policies: **P0+avoid** (mark the riskiest 2% of hosts each day; never migrate) and **P4+avoid** (BAM plus the same marks).
- Run them on the evaluation seeds of every regime (A-E, 1-30), with the same worlds and budgets, as an exploratory group after the confirmatory runs finish.
- Report them beside P0, P2 and P3 in the companion table against P0 and in F4b.
- They stay outside the 30-comparison family and the G3 rule. Nothing pre-registered changes.

Cost. Neither needs tuning, and each run takes about 1 s. All 16 regimes × 30 seeds × 3 runs take about 5 min on 8 cores.

Implementation:
- `scripts/v2/37_explore_avoid.py` runs P0+avoid at 2% and P4+avoid at 1% and 2%, on the same worlds and with the same predictor pairing as the frozen runner.
- Output: `results/explore/avoid/`, plus `results/summary/explore_avoid.json` (saving against never migrating, with BCa intervals, beside P4 and P5).
- Queued in `run_rest.sh` after the ADR-007 extension.
- The frozen runner (`24_run_matrix.py`) is unchanged.

Alternatives considered:
- **Leave it to the Discussion, with dev-seed numbers only.** Rejected: five dev seeds are too few for a result this central, and a reviewer would ask why the strongest baseline appears only in prose.
- **Make P0+avoid the comparator for G3.** Rejected: that would change a pre-registered rule after seeing results.

Consequences:
- The paper's policy contribution changes shape. "Where new VMs go matters more than which VMs move" becomes a candidate headline, decided at G3 with the advisor.
- Marking share (2%) and the noisy-predictor case become natural Week 20-style sensitivity runs for avoidance.
