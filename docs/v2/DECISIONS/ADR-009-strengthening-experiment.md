# ADR-009: the strengthening experiment is a published migration-cost range (Week 27, task 3)
Status: proposed (owner to accept; drafted 5 Oct 2026, before the B/C results exist)
Date: 2026-10-05

Context: plan Week 27 asks for one experiment that strengthens the weakest claim (`WEAKEST_CLAIM.md`). It offers two paths:
- **A second placement trace.** Done in Week 21: Google 2019 cell f, chosen by a fixed rule, τ-b −0.004, would-be class C0, which agrees with G1.
- **A measured range for migration cost.** Published live-migration measurements now, a testbed later (RQ6, Weeks 41-46).

The migration constants (link 10 Gb/s with 50% usable, dirty rate 150 MB/s at full CPU, 2 concurrent migrations, 1 s / 60 s blackout) are assumptions carried over from the prototype (`SIM_SPEC.md` section 11). Today they are varied only around their own defaults: estimation error ×0.5 and ×1.5, and the Morris ranges.

Decision (proposed): build a migration-cost range from published measurements and rerun the confirmatory regimes at its ends, as exploratory work logged in `CHANGES_AFTER_FREEZE.md`. Concretely, in Week 29:
1. From each source below, extract the measured total migration time, downtime, effective bandwidth and dirty-rate behaviour, with the setup (hypervisor, link, VM size, workload). Cite each number to a table or figure.
2. Turn them into a low / central / high setting for usable bandwidth, dirty rate and blackout. The setting is written before any rerun.
3. Rerun B1, B2 and C at 1% and 2% (P0, P2, P4, P6), seeds 1-30, at the low and high settings. That is about 2 h on 8 cores.
4. Report how far Δ and the saving against P0 move, beside the main result.

Sources (each checked on 5 Oct 2026 to exist with this title, venue and year; numbers not yet extracted, and authors marked * still to be checked against the paper itself):

| Source | Venue | Why |
| --- | --- | --- |
| Clark et al., "Live Migration of Virtual Machines" (already in `refs.bib`) | NSDI 2005 | Pre-copy downtime and total time; the model the simulator uses |
| Voorsluys, Broberg, Venugopal, Buyya, "Cost of Virtual Machine Live Migration in Clouds: A Performance Evaluation" | CloudCom 2009 (LNCS; arXiv 1109.4974) | Application-level overhead of migration on Web 2.0 workloads |
| Akoush, Sohan, Rice, Moore, Hopper, "Predicting the Performance of Virtual Machine Migration" | MASCOTS 2010, pp. 37-46 | Link speed and page-dirty rate as the main determinants of migration time |
| Liu, Xu, Jin, Gong, Liao, "Performance and energy modeling for live migration of virtual machines" | HPDC 2011 (journal version: Cluster Computing, doi 10.1007/s10586-011-0194-3) | Measured cost across five workloads on Xen |
| Hu et al.*, "A quantitative study of virtual machine live migration" | CAC 2013, doi 10.1145/2494621.2494622 | Comparison across hypervisors (KVM, Xen, VMware, Hyper-V) |
| "Towards a comprehensive performance model of virtual machine live migration"* | SoCC 2015, doi 10.1145/2806777.2806838 | Published at the target venue; reviewers will know it |

Alternatives considered:
- **A third placement trace.** Rejected for now: two sources already agree on C0, and the claim most exposed to reviewers is the cost model, not the correlation.
- **Model-based worlds** (ADR-008, deferred). They remain a candidate for Week 30 if the reviews press on the oracle (R2.1). They address a different weakness and take about a day of compute and work.
- **Testbed measurements now.** That is RQ6 in Weeks 41-46 and needs hardware; it is out of scope for Phase 6's polish cycle.

Consequences:
- Everything this adds is exploratory and outside the 30-comparison family.
- If the published range moves the B-regime result across the 1% bar, the paper says so in the Evaluation section, not only in the Discussion.
- The bibliography gains up to five entries. Each is checked against its publisher page before it enters `refs.bib`, as the Week 24 rule requires.
