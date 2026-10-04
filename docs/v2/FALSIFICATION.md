# Falsification list (draft, 4 Oct 2026; Week 2 task 8)

Three claims I hope to make, each next to the result that would show it false. This becomes section 1 of `PROTOCOL.md` in Week 3. The numeric tolerances are fixed in protocol v0 (Week 3) and the theory check (Week 17); the wording below fixes only the direction, so none of these is pre-registered yet.

## Claim 1: real placement is at or above the break-even correlation (RQ1, C1)

> In public placement traces, the rank correlation between workload criticality and host risk is high enough that workload-aware mitigation can pay off.

**Falsified if** the 95% confidence interval for the measured correlation lies entirely below the break-even level (the plan sets pH = 0.30 in Week 3, which equals v1's observed crossover at about 0.3) in the Google 2019 trace and in the second source (Alibaba 2018), under every proxy and mapping the protocol lists. The paper then takes shape 3 (little benefit) or the conditional shape, and the benchmark stands.

**Also not supported** if the interval is too wide to classify under the precision rule in Gate G1 (class decided by protocol, not after the fact).

## Claim 2: under the stated assumptions, a budget-aware policy is never worse than a tuned threshold (RQ2, C2, C3)

> With calibrated probabilities and a matched budget measured in the same resource (GB of VM memory moved), BAM-GB has an advantage of at least zero over the best of three tuned thresholds (P2), in expectation.

**Falsified if** in any simulated cell that meets the stated assumptions, the Holm-adjusted upper bound of the paired advantage over P2 is below zero, or if Monte Carlo and the closed form disagree by more than the tolerance set in Week 17. Either result means a bug or a wrong theorem, and the theory section is rewritten, not the data.

This is also the check on v1's anomaly: if v1's loss of 3.1% at correlation 0 survives matching the budget in GB and removing noise (hypotheses H1-H8, Week 3), the claim is false as stated.

## Claim 3: the guard makes the policy safe (RQ4, C3)

> A policy that does not know the correlation, using the guard P6, is never materially worse than P2.

**Falsified if** in any confirmatory regime, including the drift scenario and a pure-noise control, the lower bound of P6's paired advantage over P2 is below minus 1% at 30 or more seeds, or if P6 switches to BAM on the pure-noise control. The paper then reports the guard as future work (the last item in the cut order).

## Notes for protocol section 1

- Each claim has an opposite outcome that is still publishable (see the three paper shapes in the charter); that is the point of writing the falsifier first.
- v1 supplies the starting evidence for none of these: it used one seed, four correlation points and random placement.
