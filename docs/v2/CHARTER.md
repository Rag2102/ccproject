# Charter (v1, drafted 4 Oct 2026; Week 2 task 1)

Draft status: the wording of the thesis, RQs and contributions is taken from the v5 plan (Part I section 1). The non-goals and the reasons are mine, built from the readings in `reading/`. The Sunday test for this file is yours: read every sentence aloud and delete any you cannot defend in a minute. Lines marked **[check]** are the ones I am least sure you will want to keep.

## Goal

Produce a measured, derived and guarded answer to when workload-aware VM failure mitigation beats a tuned probability threshold, delivered as reproducible benchmark results that support a complete research paper, whatever the answer turns out to be.

## Thesis

When failure probabilities are calibrated and the ranking matches the budgeted resource, workload-aware mitigation weakly dominates a probability threshold in expectation. In practice it can lose through noisy or miscalibrated probabilities, a wrong cost model or a mismatched denominator. The project measures where real placement sits, derives the break-even as a surface over correlation, spread and estimation error, and ships a budget-aware policy with a guard that stands down when the evidence for benefit is weak.

Why this is not "our policy wins": v1 found the cost-sensitive policy 3.1% behind a matched-budget threshold when placement is random, and ahead by 3.4% when criticality tracks risk at a rank correlation of about 0.86 (`docs/v2/v1_final_state.md`). The thesis keeps both results as predictions to be tested.

## Research questions (paper A, with the benchmark and extension)

| ID | Question | Answered by | Weeks |
| --- | --- | --- | --- |
| RQ1 | Where do criticality and host risk sit relative to the break-even in real placement? | R1, R12 | 6-8, 21, 29-30 |
| RQ2 | What is the advantage surface and where does it cross 1%? Does simulation match theory? | R4, R5 | 3, 15, 17-18 |
| RQ3 | Which assumptions do the conclusions depend on most? | R8, R9 | 16, 20 |
| RQ4 | Can a policy that does not know the correlation match the better policy and never be materially worse than a tuned threshold? | R10 | 16, 21 |
| RQ6 | How far do measured migration costs move the break-even? | R14, R15 | 41-46 |
| RQ7 | How do rack-correlated failures and two budget resources change rankings and the guard's value? | R16, R17 | 47-50 |
| RQ8 | Can an outside policy be added in under an hour and compared fairly on frozen worlds? | R18, R19 | 51-54 |

The v5 plan has no RQ5; the numbering skips it and the plan does not say why. **[check]** Keep the gap so that references to v3 and v4 still resolve, or renumber.

The advantage in RQ2 is the paired per-seed difference in total cost between a policy and the tuned threshold (P2), positive when the policy is better. The break-even threshold is 1%, fixed in protocol v0 and never moved.

## Contributions

| ID | Contribution | Status |
| --- | --- | --- |
| C1 | A measurement of criticality-risk correlation (rank correlation with confidence intervals) in public placement traces, and what it implies for the break-even | Planned, weeks 6-8 |
| C2 | A break-even theory: the advantage as a surface, with a closed form checked against simulation | Planned, weeks 15-17 |
| C3 | BAM-GB, a budget-aware policy that ranks VMs by benefit per GB moved, and P6, a guard that falls back to a tuned threshold when evidence of benefit is weak | Planned, weeks 15-16 |
| C4 | VMMBench: hashed failure worlds, a plug-in policy interface, a scorer and a hidden-seed leaderboard | Planned, v0.9 in week 25, v1.0 in week 54 |
| C5 | The Research Console, a read-only view of frozen results with provenance badges. An artifact, not a scientific claim | Planned, weeks 22-34, capped at 16 hours before submission |

Not claimed as contributions: the expected-cost decision rule (it is Elkan's threshold with example-dependent costs; see `reading/elkan2001.md`) and a new failure predictor (held fixed in the main track).

## Non-goals

| Non-goal | Reason |
| --- | --- |
| A claim about production performance at any cloud provider | The data are public (Backblaze drives, Google and Alibaba traces) and the evaluation is simulated; the plan states "no deployment claim". Narya's own numbers are proprietary and relative only (`reading/levy2020narya.md`). |
| Re-implementing Narya | Its data, rules and thresholds are not public. P5 is a Narya-inspired baseline whose differences from the paper are logged in Week 15. |
| A better failure predictor | The main track holds the calibrated predictor fixed so that differences come from the policy; the predictor is varied only in a separate track (RQ3). Disk-failure prediction is its own literature (for example Xu et al. 2018). |
| A learned (reinforcement-learning) policy as the method | v1 excluded it, and P5 stays a baseline. Production systems such as Narya, NENYA and Deoxys already use learned policies on private data. |
| Software or non-hardware failures | Narya also targets hardware and firmware failures only (section 9); the public data cover drives, not other failure causes. **[check]** The plan's non-disk hazard term is a sensitivity parameter, not a model of software failures. |
| Network topology and cross-host contention beyond the budget resources in the plan | v1 excluded them and I have not seen the v5 simulator specification (written in Week 9). **[check]** Revisit when `SIM_SPEC.md` exists. |
| Moving the 1% materiality threshold after seeing results | Fixed in protocol v0; changes go to `CHANGES_AFTER_FREEZE.md` and are exploratory. |

## Scope and rules that hold throughout

Public data plus simulation, with a small local testbed in the extension phase. Every outcome has a paper (pays off, conditional, little benefit). Every week ends in a file you can point to. Anything that differs between the v5 plan and older documents is decided by v5.
