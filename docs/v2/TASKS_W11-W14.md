# Tasks, Weeks 11-14

From the v5 week cards for W11-W14. Built on 4 Oct 2026, ahead of the calendar (W11 starts 14 Dec), while the Week 7 and Week 8 runs were going. `[x]` = done and checked; `[~]` = done, needs you; `[ ]` = not done.

## Week 11 (14-20 Dec): simulator core

- [x] `vmsim/` package: `config` (frozen dataclasses, YAML, unknown keys rejected), `rng` (named streams from one SeedSequence), `entities` (structures of arrays; Azure VMs resampled jointly), `placement` (random, v1's blend with a target rho, adversarial, trace)
- [x] Placement hits its rho target within 0.02 at 0, 0.15, 0.30 and 0.45 (tests)

## Week 12 (21-27 Dec): failure process, predictors, failure worlds

- [x] `failure` (drive hazard from v1's lookup, Weibull non-disk term, exact inverse-transform failure times), `predictor` (oracle, noisy, miscalibrated), `worlds` (generate, save with SHA-256 and manifest, load)
- [x] Self-calibration over 1,000 hosts; CRN across placements; shape check recorded (`results/v2/shape_check.json`)
- [ ] `TrainedModel` predictor and drive hazards from the Week 7 model: waits for the model choice (`failure_model_v2.md`, decision for you)
- [ ] Failure worlds for eval seeds 1-30: after the model is plugged in and the pilot sets the scale

## Week 13 (28 Dec-3 Jan): migration, accounting, v1 regression; Gate G2

- [x] `migration.py`: pre-copy rounds after Clark et al., per-host lanes, v1's closed form (v1's per-VM costs reproduced to 2 × 10⁻¹⁶)
- [x] `accounting.py`: realised costs; `outcomes.parquet`, `daily.parquet`, `summary.json` with git SHA, config hash, seed and an outcomes SHA-256
- [x] `engine.py`: day-stepped, exact times inside each day; repairs and repeat failures; residents and transients (`SIM_SPEC.md` v0.2 lists the design changes)
- [x] v1 regression: 456,533 and 442,701 to 6 × 10⁻⁷, migration counts exact (`vmsim/v1_regression.py`)
- [x] Property tests (`hypothesis`) for the invariants, checked on every simulated day; determinism, CRN, zero budget, tie order, oracle bounds, self-calibration across repairs
- [x] Run time: 2.0-4.8 s per run at 5,000 hosts × 365 days (target 10 s); v1 scale 12.7-18.4 s and 7.3 GB
- [x] Shape check with repeat failures: per-node uptime shape 0.94-0.98 (node logs about 0.7-0.8, to verify)
- [~] `G2_simulator_validation.md` (Table 4): all five criteria met. **Needs your sign-off with the advisor**; then tag `sim-v2.0`
- [x] Paper: `paper/sections/simulator.tex` (draft)
- [x] CI: `requirements-dev.txt` gains pyyaml, hypothesis and pyarrow, without which `tests/v2` cannot run in CI

## Week 14 (4-10 Jan): reference policies, budget, pilot

- [x] Policy interface: `decide(obs, budget_gb)` returns VMs in priority order; the engine applies the budget, picks destinations and times migrations
- [x] P0, P1 (tau = 0.0073), P2 (tuned), P3 (v1 rule, survival-weighted), P7 (oracle), P8 (random)
- [x] Budget in GB at 0.5/1/2/5%, filled in each policy's order (exact-budget rule); counts logged daily
- [x] Sanity tests: zero budget = P0; P7 not worse than any policy on seeds, and not worse with more budget; P8 not better than P2 on 10 seeds (with P2 tuned on cost; see below)
- [x] A regimes on the latent axis (`vmsim/copula.py`, `vmsim/scenarios.py`): A3 = Spearman 0.256 under the simulator's margins
- [~] **Decision for you: how P2 is tuned.** The protocol says "tuned to use the budget". Tuned that way, P2 spends nearly the whole budget on unneeded migrations and costs more than never migrating; with smallest-first it even loses to random. Proposal: tune tau and order to the lowest cost on dev seeds (P2c), so the comparator is the strongest threshold policy. Both are in the pilot.
- [x] Pilot (4 Oct; seeds 201-205, 2,000 hosts × 365 days, A1 and A3 at 2%; `results/v2/pilot_w14.json`):
  - P2 tuned to use the budget (tau ≈ 0.013) costs about 3.9× never migrating (A1: 123,643 vs 31,906); migration cost dominates under v1's cost constants. P2c tuned on cost: tau = 0.32 at A1 (never migrates, = P0) and 0.10 at A3 (2.4% below P0)
  - SD of Delta, P3 vs P2c: 1.3% (A1), 3.8% (A3). Against the protocol's Bonferroni column (30 seeds: 1.6%; 100 seeds: 3.1%), A3 at this scale does not meet the bound: the design must grow (hosts or horizon), per the protocol's rule
  - achieved correlation of the VMs present at A3: 0.217 against the 0.256 target (arrivals dilute it)
  - P7 ≤ every policy and P8 ≥ P2 on every cell; per-run time 0.9-3.2 s
- [ ] Scale ADR (`docs/v2/DECISIONS/ADR-005-scale.md`) from the pilot's SD of Delta: hosts, horizon and number of eval seeds (queued after the pilot, not started)
- [ ] B1 pilot cell: after Week 8's rho
- [ ] Smoke grid P0-P3, P7, P8 on 5 seeds in regime A: the pilot table doubles as the smoke grid
