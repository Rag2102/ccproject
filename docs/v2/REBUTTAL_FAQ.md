# Rebuttal FAQ (Week 39, task 4): drafted 26 Oct 2026

The ten questions reviewers are most likely to ask, each with a short answer and where the evidence is. Drafted before the B/C, Week 20 and Week 21 results exist. **Answers marked ⏳ depend on those runs; re-check every number against `paper/numbers.tex` before the rebuttal phase, and quote macros, not this file.** The mock-review ids (R1.x-R3.x, `feedback.csv`) show where each question was raised first.

---

**1. Isn't the tuned threshold a straw man? It costs more than doing nothing.** (R3.2)
Yes, P2 as pre-registered (tuned to use the budget, ADR-005) costs more than never migrating in every seed, and the paper says so first. That is why every comparison is also reported against never migrating (Table `tab:vsp0`, F4b) and against the v1 rule P3. The headline the paper leads with is the saving against P0, not Δ against P2. Tuning P2 on cost instead was considered before any evaluation run and rejected because it would have changed a pre-registered rule after the pilot. *Evidence:* ADR-005; `RESULTS_W18.md`; `evaluation.tex` (A/E paragraph).

**2. The main matrix uses true probabilities. Isn't the headline an upper bound?** (R2.1) ⏳
It is, deliberately (ADR-008): the oracle isolates the decision rule from model error, so the comparison between rules is fair. Week 20 then replaces it with noisy, miscalibrated and drifting predictors and the trained ensemble, and reports how far each result moves. *Evidence:* Week 20 robustness grid (appendix `app:robust`), F7; ⏳ quote the noisy-predictor result once run.

**3. Your own bandit (P5) and a simple "avoid risky hosts" rule beat your method. What is the contribution?** (R3.4)
The finding is the contribution. A pre-registered comparison of migration ranking rules shows that, in this simulator, *where new VMs go* matters more than *which VMs move*: keeping arrivals off the riskiest 2% of hosts saves more than any migration policy, with no migrations (exploratory, all 30 evaluation seeds, every A and E regime). The theory still explains when cost-aware migration helps (spread of cost per GB), and the measurement (ρ ≈ 0 in real traces) still holds. *Evidence:* `RESULTS_AVOID.md`, `DIAG_P5_VS_BAM.md`, ADR-010; F4b.

**4. Is avoidance free? Marked hosts must cost capacity.**
Not entirely. Rejected arrivals rise by up to about a quarter in the tightest regimes (A3: 152 → 160 per run; A7: 114 → 140), and the simulator charges only for the arrivals lost, not for stranded capacity. The paper states this as the main caveat of the avoidance result. *Evidence:* `RESULTS_AVOID.md`, point 4.

**5. Is the experiment powered? 30 seeds seems few.** (R1.3) ⏳
The number of seeds was set by a pilot on seeds used nowhere else, so that the seed-to-seed SD of Δ sits below the Bonferroni bound (1.6% at 30 seeds), with a rule fixed in advance that extends any regime to 50 seeds when it does not. The rule fired for A3 and A5 (because of P5 and P6, not BAM), so those regimes are extended to 50 seeds (queued in `run_rest.sh`). *Evidence:* ADR-007; appendix `app:pilot`; ⏳ the 50-seed rerun.

**6. You measure drives, but hosts fail.** (R1.2)
Host risk is composed from its drives plus a non-disk term (Weibull, set relative to the disk hazard), and the non-disk multiplier is varied 0×, 1× and 3× in Week 20. Drive-level telemetry is the only public source with real failure labels at this scale. *Evidence:* SIM_SPEC sections 7 and 11; Week 20 sensitivity ⏳.

**7. Google's placement is one operator in one year. Does ρ ≈ 0 transfer?**
Two sources agree: three G1 cells (|τ_b| ≤ 0.075 under every mapping and proxy) and a fourth cell chosen by a fixed rule and analysed separately (τ_b ≈ 0). The paper claims only that real placement in these traces ignores hardware risk, and the B regimes bracket the measured value with its confidence bounds. *Evidence:* `G1_decision.md`; second-source result (Week 21); B1-low/B1-high.

**8. The migration cost model is assumed. Would published measurements change the answer?** (R1.1) ⏳
The constants come from the prototype, so they are bracketed with a range built from published live-migration measurements (ADR-009): B1, B2 and C are rerun at the cheap and expensive ends of that range (one of six sources extracted so far). *Evidence:* `configs/v2/cost_range.yaml`, `run_w30.sh`; ⏳ quote how far Δ and the saving against P0 move.

**9. Isn't budget-aware ranking just Dantzig's greedy knapsack with Elkan's cost-sensitive rule?** (R3.1)
The ranking rule is classical and the paper says so. What is new is (a) the measurement of the correlation that decides whether it matters, (b) a closed form for its advantage over a threshold that shows the driver is the spread of cost per GB, checked by Monte Carlo at every grid point, and (c) a pre-registered, open benchmark. The results also show the budget never binds, so BAM's gain comes from its stopping rule (b > 0), not from ranking. *Evidence:* THEORY.md; `related.tex`; `evaluation.tex`.

**10. Can we reproduce it?** ⏳
Yes. Every number in the paper is a generated macro; a clean clone rebuilds every summary and number byte for byte from the committed per-cell results (`scripts/v2/final_check.sh`); a reduced version of every main figure runs in under an hour on a laptop; the full study takes about 14 hours on eight cores; a Docker build is set up to reproduce Table 3 (small) in a clean container (it runs at the end of `run_rest.sh`; not yet run). *Evidence:* artifact appendix; `make reproduce-small`, `make final-check`, `make docker-repro`.

---

Not in the ten, but ready: the regression adjustment is pre-treatment (R2.2, closed); exploratory cells are labelled and outside the family (R2.3); the last rolling fold of the failure model is weaker and is covered by the noisy-predictor sweep (R2.5).
