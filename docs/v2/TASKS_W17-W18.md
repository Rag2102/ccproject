# Tasks, Weeks 17-18

From the v5 week cards for W17 and W18 (plan page 19-20). Built on 4 Oct 2026, ahead of the calendar (W17 starts 25 Jan 2027). `[x]` = done and checked; `[~]` = done, needs you; `[ ]` = not done.

## Week 17 (25-31 Jan): theory, protocol freeze, code freeze, runner

- [x] **THEORY.md** (`docs/v2/THEORY.md`): A1-A4 and the accounting assumption.
  - T1 (density ranking optimal for the knapsack relaxation, greedy within one item) and T2 (Delta ≥ 0 under A1-A4) are proved.
  - T3 closed form under a Gaussian copula on (log p, log κ), in `vmsim/theory.py`.
  - T4 is partly false as stated: noise alone never flips the sign at ρ ≥ 0, and moderate noise often raises Delta. A flip needs ρ < −σ_κ/σ_p or flattening miscalibration (γ < 1).
- [x] **Numerical check** (`scripts/v2/theory_check.py`): 3,024 grid points over (ρ, σ_logκ, q, λ, σ_noise, γ), Monte Carlo against closed form.
  - Tolerance set before the sweep: |Δ_MC − Δ_CF| ≤ max(3 SE, 0.001).
  - 13 points missed at first; all agree when rerun with 80 replicates (`theory_recheck.json`).
  - T2: the smallest no-noise Delta is +0.0006.
  - Figure: `results/figures/v2_theory_check.pdf`.
- [x] **Anomaly closed** (THEORY.md section 5, `v1_anomaly.md` final section). v1 broke A3 (budget) and the horizon accounting. With both repaired, the +0.2% it shows is what T3 predicts once diluted by the 3.4% of v1's total cost that a 30-day decision can touch. The two-sentence answer is in THEORY.md section 5.
- [x] **Break-even surface** (THEORY.md section 3): Delta = 1% needs σ_logκ ≳ 0.3; above that it holds for |ρ| below about 0.86-0.97. For interpretation only; G1 = C0 stays final.
- [~] **Freeze.** `PROTOCOL.md` v1.0 is written: matrix in `configs/v2/matrix.yaml`, n from the pilot (ADR-007), budgets, ablations, robustness and sensitivity grids, confirmatory family, protocol-failure rule, analysis scripts, Console schema. `CHANGES_AFTER_FREEZE.md` is started. **Tags `protocol-v1.0` and `v2.0-rc1` are yours** (commands in the reply). OSF registration is optional and yours.
- [x] **Runner** (`scripts/v2/24_run_matrix.py`): phases cards, tune, run and collect; `--shard i/N`, resumable by record file; one vmmbench/1 record per run; one Parquet per cell; manifest with SHA-256.
- [x] **Dry run** of the whole matrix (4 Oct, 22:21-23:01; `results/dryrun/`, log `results/dryrun/dryrun_log.txt`). 16 regimes × 4 budgets × 9 policies × seeds 1-2: 1,056 runs, 528 of 528 cells complete. No crash, no overspend, every record valid against vmmbench/1. `30_stats.py` and `31_fig_f4.py` run end to end on it. About 197 core-seconds per (regime, seed). B1-low is identical to A1 by construction: its latent target is below 0, so placement is random.
- [x] **Paper:** `paper/sections/approach.tex` (BAM, P6 and the theory statements that survived).
- Gaps from earlier weeks closed here:
  - Week 10 schemas (`vmmbench/schemas/*.json`, validator `vmmbench/validate.py`, test `tests/v2/test_vmmbench_schemas.py`);
  - regime E (cost spread) and B2 (class-conditional replay from the trace), both tested;
  - **a bug in the latent axis:** the tier margins were the resident pool's (49/27/24%), not the VMs present (61/4/35%). Fixed, and A, B1 and D recalibrated before any evaluation run.
- Decisions recorded:
  - ADR-005: P2 by budget;
  - ADR-006: ensemble chosen, rule before result;
  - ADR-007: 2,000 hosts × 365 days, n = 30, SD-triggered extension;
  - ADR-008: oracle for the main matrix, model-based worlds in Week 20;
  - natural cost spread in A;
  - P5 = faithful variant (dev-seed rule);
  - P6 fallback P2.

## Week 18 (1-7 Feb): benchmark runs I, regimes A1-A7 and E

- [ ] Launch A1-A7 and E1-E3: all policies, 4 budgets, eval seeds 1-30, 8 shards → `results/raw/A/`, `results/raw/E/`
- [ ] Monitor completeness only (`results/raw/completeness.csv`)
- [ ] Statistics: `scripts/v2/30_stats.py --groups A E` → `results/summary/A.json`, `E.json`, `confirmatory.json` (partial family, provisional), `vmconsole.json`
- [ ] F4: `scripts/v2/31_fig_f4.py` → `results/figures/v2_F4_advantage.pdf` (simultaneous CIs, per-seed dots, T3 overlay at the simulator's measured parameters)
- [ ] Regime E verdict against H7 and H8
- [ ] Results paragraph for A and E, written before B and C are seen
- [ ] Backup of `results/raw/` (second location) and the manifest
