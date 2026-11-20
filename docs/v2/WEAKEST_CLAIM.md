# The weakest claim (Week 27, task 2): provisional

Rule (plan Week 27): take the claim from `CLAIMS_LEDGER.md` with the widest interval or the most assumptions, and write why.

**Provisional choice: C3a.** In the realistic regimes (B1, B2), BAM does or does not beat the budget-tuned threshold by ≥ 1%. Written 5 Oct 2026, before the B/C results exist. The choice is re-checked once `results-frozen` exists; if the intervals point elsewhere, this file changes and says why.

Why C3a:
1. **It carries the most assumptions.** Every row of the paper's assumed-elements table (`tab:assumed`) feeds it: drive-composed host risk, the non-disk term, repair times, tier weights, downtime, the migration constants, initial fill and the risk horizon. The theory claims (C2a-C2c) rest on four stated assumptions. The measurement (C1) rests on one proxy, already varied three ways.
2. **It uses the oracle predictor** (ADR-008). It is an upper bound under calibrated probabilities, and the trained model enters only as robustness settings (R2.1).
3. **Its comparator is contested** (ADR-005; R3.2). The budget-tuned P2 can cost several times more than never migrating, so the size of Δ against P2 says little on its own. The companion comparison against P0 is the number a skeptic will read.
4. **Its most uncertain inputs are the ones least measured.** The migration constants come from the prototype and have never been checked against a measurement. That is why ADR-009 proposes a published cost range.

The runner-up is C3b, the guard on regime D. Its D regime is fully synthetic (drift at mid-run), and its fallback is the expensive P2.

To re-check after the runs: the claim with the widest simultaneous interval in Table 3 and the largest Morris μ* exposure.
