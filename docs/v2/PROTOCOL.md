# Protocol v1.0 (frozen 4 Oct 2026, Week 17; v0 tagged `protocol-v0`)

This protocol fixes every decision rule before any evaluation-seed result is seen. Version 0 was the draft sent to the advisor in Week 3. **Version 1.0 is frozen** (tags `protocol-v1.0` and `v2.0-rc1`). After the freeze, every change goes to `CHANGES_AFTER_FREEZE.md`, and results produced under a change are exploratory. The matrix is `configs/v2/matrix.yaml` (section 10); decisions behind it are ADR-005 to ADR-008.

Sources: v5 plan Part I sections 1-5, the week cards for W3, W14-W17 and W21, and the gate table carried over from v3 section 3.3. Where this file adds a rule, it says so and gives the reason. Items still open are marked **[set in Wn]** with the week that fixes them.

## 1. Claims and what would falsify them

Copied from `docs/v2/FALSIFICATION.md` (Week 2). Tolerances set in Week 17 are marked.

| Claim | Falsified if |
| --- | --- |
| 1. Real placement is at or above the break-even correlation (RQ1, C1) | The 95% CI of the measured correlation lies below pH = 0.30 in Google 2019 and in the second source, under every proxy and mapping (G1 class C) |
| 2. Under the stated assumptions, BAM-GB is never worse than a tuned threshold (RQ2, C2, C3) | In any cell meeting assumptions A1-A4, the Holm-adjusted upper bound of Delta vs P2 is below 0; or Monte Carlo and the closed form disagree beyond the tolerance: \|Delta_MC − Delta_CF\| > max(3 SE, 0.001) at a point that still fails when rerun with 8× the replicates (`THEORY.md` section 4) |
| 3. The guard P6 makes the policy safe (RQ4, C3) | In any confirmatory regime, including D and a pure-noise control, the lower bound of P6's Delta vs P2 is below -1% at n >= 30; or P6 switches on the pure-noise control |

Week 3 evidence bearing on claim 2: in v1's simulator with calibrated synthetic p and 30-day accounting, the v1 rule (BAM at its own operating point) was ahead of the threshold on 10 of 10 seeds (`docs/v2/v1_anomaly.md`, H5). Under v1's original accounting it was behind on all 10. That is why section 4 fixes the accounting.

## 2. Policies

| ID | Policy | Role |
| --- | --- | --- |
| P0 | Never migrate | Floor for "benefit captured" |
| P1 | Fixed threshold tau = 0.0073 (v1's 95th percentile) | v1 continuity |
| P2 | Tuned threshold: best of three within-host orders (smallest-first, largest-first, random), tau tuned by bisection on dev seeds 101-110 to use the budget (utilisation ≥ 0.95), per regime and budget (ADR-005) | **The comparator for every Delta** |
| P3 | v1 cost-sensitive rule (p * F * urgency > M) | v1 continuity |
| P4 | BAM-GB: for each VM b = p * c * e - m and w = GB; rank by b / w; fill while b > 0 and budget remains; recompute e for the host's queue after each pick | **Primary method** |
| P4-time, P4-cost | BAM with w = NIC-seconds, or w = m (the v2 rule) | Ablations only |
| P5 | Narya-inspired: actions {nothing, live-migrate, avoid-allocation}, risk buckets, Thompson sampling; differences from the paper listed in `narya_differences.md` (W15). **The faithful variant** (NoOp / UA / UA-LM, Gamma-Poisson), chosen because its mean cost on dev seeds 101-105 was lower (33,677 against 36,938 for the simple variant; A3, 2%) | Strongest fair competitor |
| P6 | Safe-adaptive guard: BAM only when the CI lower bound of its plug-in Delta over P2 is > 0 and the calibration audit passes on two consecutive looks; otherwise P2 (the fallback stays P2, owner 4 Oct). Looks every 7 days, alpha 0.05 spent as 6 alpha / (pi² k²), 500 host-bootstrap resamples, audit slope band [0.8, 1.25] over a rolling 90 days with at least 30 events | Method (RQ4) |
| P7 | Oracle | Ceiling for "benefit captured" |
| P8 | Random selection within the budget | Sanity floor |

Rules added from the Week 3 diagnosis (`v1_anomaly.md`):

- **Exact budget.** Every policy, P2 included, spends the budget in the budgeted resource (GB) to within one VM, filling the remainder in its declared within-host order. v1's bisection missed the count by 8%, which was worth about 1 point of Delta.
- **Budget use is reported.** Any run that leaves more than 5% of its budget unspent (for example BAM stopping at b <= 0) reports the unspent share next to Delta (adopted in v1.0; `30_stats.py` reports it per cell).
- **Sanity checks (W14).** With zero budget, every policy equals P0. The oracle is never worse than any policy, and its cost does not increase with budget. P8 is never better than P2 in expectation (checked on 10 seeds). Under uniform c and m with no urgency, `--p-only` BAM equals P2 decision for decision.

## 3. Regimes, budgets and design

| ID | Placement | Parameters | Use |
| --- | --- | --- | --- |
| A1-A7 | Synthetic latent Gaussian copula | rho_L in {0, .15, .3, .45, .6, .75, .9}, converted to Spearman under the margins of the VMs present (61/4/35%); the arrival blend calibrated so the VMs present hit the target under P0 (`results/v2/regime_calibration.json`); sigma_log_kappa natural, 1.06 (Azure sizes and v1's tier weights; owner, 4 Oct: v0's 0.5 was a placeholder) | Advantage curve; theory check |
| B1 | Rank copula calibrated on measured rho and dispersion | Latent rho from G1 (M1, platform proxy): B1-low -0.019 (lowest lower bound; placement random, since the blend cannot go below 0), B1 0.007 (median point), B1-high 0.056 (highest upper bound) | Realistic regime (confirmatory: B1 point) |
| B2 | Class-conditional replay | Host class = Google 2019 machine platform; hosts assigned to classes by risk rank with the measured machine shares; P(class \| tier) from the trace's class x tier table fitted by IPF to the simulator's margins (odds ratios kept; `results/v2/b2_classes.json`) | Second realistic variant (confirmatory) |
| C | Adversarial | Critical VMs on the riskiest hosts | Upper range of benefit (confirmatory) |
| D | Non-stationary | rho_L 0.1 to 0.6 mid-run; predictor drifts from gamma 1 to 0.7 over the second half | P6, adaptive track |
| E1-E3 | Heterogeneity only | rho_L = 0 (random placement); sigma_log_kappa in {0.25, 0.5, 1.0}, set by rescaling each VM's interruption cost around the reference median of log(c / w), keeping its order | Isolates cost spread; explains v1 at rho = 0 |
| G, R1-R3, M | Extension (v4) | Measured costs; rack shocks; two budgets | Paper B; not part of this protocol's confirmatory family |

Budgets: 0.5, 1, 2 and 5% of cluster memory per day. **Scale (ADR-007):** 2,000 hosts, 4 drives per host, 365 days + 30 warm-up, H = 30. **Predictor (ADR-008):** the oracle on the validated hazards for every regime (D: the drifting predictor). Model-based worlds from the ensemble (ADR-006) are a Week 20 robustness run, exploratory. Each regime's scenario card is in `configs/v2/cards/` with its SHA-256 in every result record.

## 4. Metrics and accounting

| Metric | Definition | Role |
| --- | --- | --- |
| Total cost | Weighted interruption cost + migration cost (tier weight x minutes; bandwidth term in minutes-equivalent) | Primary |
| Delta vs P2 | Per seed s: (C_P2,s - C_pi,s) / C_P2,s; positive means pi is better; raw and regression-adjusted on realised failures | Primary comparison |
| Benefit captured | (C_P0 - C_pi) / (C_P0 - C_P7) | Leaderboard |
| Missed failures | VMs interrupted without a prior completed migration (weighted and unweighted) | Secondary |
| Unnecessary migrations | Migrations whose source did not fail within H days | Secondary |
| Budget utilisation | GB migrated / budget; any overspend makes a run invalid | Validity |
| Regret; switches | Against the best fixed policy in hindsight; number and timing of P6 mode changes | Adaptive track |

Accounting rules added from the Week 3 diagnosis (the main cause of v1's -3.1%):

1. **One horizon.** The horizon H of the failure probability a policy sees is the horizon over which a migration is credited. A migration averts an interruption only if the source host fails within H days of the decision; otherwise it is an unnecessary migration. In v1 the same choice moved Delta from -2.1% (any later failure credited) to +0.2% (30-day credit).
2. **VMs leave.** VM departures are simulated (`SIM_SPEC.md`, W10). A migration protects only the VMs on the host at the time, and only while they would have run. In the v1 trace the median VM lives 40 minutes.
3. **Theory states its accounting.** T2 (Delta >= 0 under A1-A4) is proved for the accounting in rule 1; THEORY.md (W17) states this as an assumption.

## 5. Statistics

- **Pairing.** Same seed means the same failure world for every policy; all comparisons are paired.
- **Materiality.** delta = 1%, fixed here and never moved. The design (seeds, hosts, horizon) adapts instead.
- **Win criterion.** A policy wins in a cell if the mean Delta is >= 1% and the Holm-adjusted lower bound is > 0.
- **Confirmatory family.** 30 comparisons: {P4, P5, P6} x {A3, A5, B1, B2, C} x {1%, 2%} budgets, each against P2. Holm correction on one-sided Wilcoxon signed-rank p-values (H1: Delta > 0) of the regression-adjusted Delta for decisions; Bonferroni-simultaneous BCa intervals (level 1 − 0.05/30) for plots. **Operational win:** mean adjusted Delta ≥ 1% and Holm-adjusted p < 0.05. Everything else is exploratory and labelled. Holm runs once over all 30; partial runs (Week 18, A only) are marked provisional.
- **Variance reduction (pre-specified).** Common random numbers, a longer horizon, and regression adjustment of Delta on the realised host-failure count (identical across policies under CRN). Raw and adjusted Delta are both reported; the decision uses the adjusted one (adopted in v1.0).
- **Display.** No bare means: every estimate has an interval, n and its family. At least one figure shows per-seed dots. Negative and null results are reported.
- **Seed families, never mixed.** dev 101-110 (tuning P2's tau and within-host order, P6's audit band, any submitted policy); pilot 201-205 (Week 14 only, then discarded); eval 1-n (n >= 30, set by the pilot); replication 1001 to 1000 + n; hidden 9001-9100 (leaderboard only; only a SHA-256 commitment is published). The Week 3 diagnostics used dev seeds only.
- **Protocol failures (rule written in Week 17).** A crashed run or an invariant violation is a bug. The bug is fixed, logged in `CHANGES_AFTER_FREEZE.md`, and **every policy** of the affected (regime, seed) is rerun from the same seed, so pairing is kept. If a run cannot be repaired, the seed is reported as missing for that regime, and the cell is decided on the remaining seeds only if n ≥ 30 still holds; otherwise it is inconclusive. No seed is ever dropped or rerun because of its result.

## 6. Power plan

The lower bound clears 0 for a true mean Delta of 1% only if the SD of Delta across seeds is below these values:

| Seeds | Max SD, uncorrected | Max SD, Bonferroni over 30 |
| --- | --- | --- |
| 30 | 2.7% | 1.6% |
| 50 | 3.5% | 2.1% |
| 100 | 5.0% | 3.1% |

Rule: the Week 14 pilot (seeds 201-205, cells A3 and B1 at 2%) measures SD(Delta) of P3 vs P2 as a proxy, and chooses n, hosts and horizon to meet the Bonferroni column. delta never moves; if the bound cannot be met, the design changes (longer horizon, more hosts), not delta.

**Decision (ADR-007):** SD 0.67% (A3) and 1.22% (B1) at 2,000 hosts × 365 days, so n = 30. **Extension rule:** if the observed SD(Delta) of any confirmatory comparison exceeds 1.6%, its regime is extended to n = 50 (seeds 31-50) for every policy, and decided against 2.1%. The trigger is the SD only, never Delta.

Exploratory prior from Week 3 (v1's simulator, not v5's): SD of Delta was 0.06-0.33 point across placements and 0.10-0.39 point across synthetic failure worlds, far inside the 30-seed bound. The pilot still decides.

## 7. Gates

### G1 (Week 8): where does real placement sit?

The measured correlation (Kendall tau-b and tie-corrected Spearman, 95% cluster bootstrap over machines with 2,000 resamples) is mapped to the latent rho_L with the provisional curve (W11) and compared with pH = 0.30 (provisional).

| Class | Condition | Consequence |
| --- | --- | --- |
| A, above | CI lower bound > 0.30 | "Pays off under realistic placement": full paper; selective venue if G3 agrees |
| B, straddle | 0.30 inside the CI, or CI width > 0.30 (unresolved) | "Conditional benefit": add a window or a second trace before closing G1 |
| C1, below (near) | CI upper bound < 0.30 and >= 0.20 | Measurement + safe policy |
| C0, below (negligible) | CI upper bound < 0.20 | Measurement + safe policy + benchmark |
| D, no trace | No usable risk proxy after the Week 8 fallback (Alibaba 2018 or tier mix) | Synthetic and adversarial regimes only; venue ceiling drops |

**Axis (v0.2, 4 Oct 2026, before any trace estimate; confirmed by the owner).** pH = 0.30 is v1's achieved tie-corrected Spearman under v1's margins. G1 compares on the latent Gaussian-copula axis: pH_L = 0.375 (and the 0.20 boundary converted the same way) against each cell's τ-b mapped to ρ_L under that cell's margins (`rho_definition.md`, step 6). The CI-width rule (> 0.30 means B) is applied on the latent axis.

**Combining cells (confirmed 4 Oct 2026).** Each cell analysed gets its own class from the table above, using mapping M1 and the primary proxy (`rho_definition.md`). The G1 class is the class held by a strict majority of those cells. If no class has a majority, the G1 class is B (unresolved): a split across cells is treated the same way as a CI that straddles pH. A cell with no usable risk proxy counts as D. Every cell's class and interval is shown in `G1_decision.md`, not only the majority.

The class assigned at G1 is final. The Week 17 break-even replaces pH for interpretation only, never for re-classification. I read the C0 boundary as "CI upper bound < 0.20" (the source writes "C0 if < 0.20"); confirm.

### G2 (Week 13): can the simulator be trusted?

All five must hold, or each failure is explained in writing:

1. Analytic degenerate-case checks pass.
2. Self-calibration: simulated 30-day failure counts over 1,000 hosts match predicted probabilities within a binomial tolerance.
3. v1 regression within 1% of v1's headline numbers, or every difference documented as intended. The Week 3 reproduction shows v1 itself reproduces to the last digit, so any gap is the new simulator's.
4. Invariants and determinism: VM conservation, no capacity violation, monotone time, no migration to a down host, byte-identical output for identical seeds.
5. Run time within the budget set in Week 10.

If not, Week 14 does not start; Weeks 14-15 fix it and the cut order applies. "G2-late" may close by Sunday 10 Jan 2027 without triggering cuts. Record: `G2_simulator_validation.md`, tag `sim-v2.0`.

### G3 (Week 21): how strong is the evidence?

| Verdict | Condition | Paper shape |
| --- | --- | --- |
| Strong | The win criterion holds for BAM or P6 over P2 in at least one real-trace regime (B1 or B2), theory matches simulation within tolerance, the seed replication agrees, and a second placement source agrees | 1, pays off |
| Medium | Wins only in synthetic or adversarial regimes while real rho is below break-even; theory matches | 2, conditional |
| Weak | No robust effect, or theory and simulation disagree | 3, little benefit, plus the benchmark |

Record: `G3_decision.md`, tag `results-frozen`.

## 8. Change control

- `protocol-v0`: sent to the advisor in Week 3.
- v0.1 (4 Oct 2026): G1 cell-combination rule added (section 7), confirmed by the owner. Still before any trace data is read, so not a post-freeze change.
- v0.2 (4 Oct 2026): G1 axis made precise (section 7): pH = 0.30 is on v1's Spearman axis and is converted to the latent axis (0.375). Written before any trace estimate; confirmed by the owner on 4 Oct 2026.
- v1.0 (4 Oct 2026, Week 17): frozen with the matrix (section 10), n from the pilot (ADR-007), budgets, ablations, robustness and sensitivity grids, confirmatory family, analysis scripts and Console schema. Before the freeze, also: P2 by budget (ADR-005), model choice (ADR-006), the oracle for the main matrix (ADR-008), natural cost spread in A, P5 = faithful variant by the dev-seed rule, P6 fallback P2, tier margins of the latent axis corrected (VMs present, not the resident pool) and the regimes recalibrated. No evaluation-seed result existed before any of these.
- `protocol-v1.0`: tag on the freeze commit.
- After the freeze: `CHANGES_AFTER_FREEZE.md`; results produced under a change are exploratory.

## 9. What is run when (Weeks 18-21)

| Week | Runs | Family |
| --- | --- | --- |
| 18 | A1-A7 and E1-E3, all policies, 4 budgets, eval seeds 1-30 | A3, A5 cells confirmatory; the rest exploratory |
| 19 | B1-low, B1, B1-high, B2, C, D, same policies, budgets and seeds | B1 (point), B2, C confirmatory |
| 20 | Ablations: BAM without urgency (`urgency=False`), without criticality (`c_uniform`), with uniform migration cost (`m_uniform`), p-only, BAM-time, BAM-cost; regimes A1, A3, A5 and B1, budgets 1% and 2%, eval seeds | Exploratory |
| 20 | Robustness: bandwidth and dirty rate ±50%; miscalibration gamma in {0.5, 1, 2}; noisy predictor sigma in {0.25, 0.5, 1, 2}; H in {7, 14, 30}; non-disk hazard 0x, 1x, 3x; tier-weight vectors (1.0/0.6/0.3, 1/1/1, 10/3/1); model-based worlds from the ensemble (ADR-008); regimes A3 and B1 at 2% | Exploratory |
| 20 | Global sensitivity: Morris screening (r = 20 trajectories) over about 10 parameters (bandwidth, dirty rate, D_fail, repair median, non-disk multiplier, concurrency, init fill, budget, gamma, sigma); Sobol on the top four if compute allows | Exploratory |
| 21 | Replication: the confirmatory cells on seeds 1001-1030 | Replication of the family |

## 10. The matrix and the analysis scripts (frozen)

- **Matrix:** `configs/v2/matrix.yaml` (scale, budgets, seeds, regimes, policies, P6 settings, the confirmatory family). Scenario cards: `configs/v2/cards/<id>.yaml`.
- **Runner:** `scripts/v2/24_run_matrix.py` (phases cards, tune, run, collect; sharded, resumable). One vmmbench/1 record per run (`vmmbench/schemas/vmmbench_result.schema.json`), one Parquet per cell (regime, budget, policy), and `results/raw/manifest.csv` with SHA-256 per file. (The plan names it `20_run_matrix.py`; that number was taken by the Week 16 guard smoke.)
- **Statistics:** `scripts/v2/30_stats.py` (section 5 exactly) → `results/summary/<group>.json`, `confirmatory.json`, and `vmconsole.json` (vmconsole/1).
- **Theory:** `scripts/v2/theory_check.py`, `vmsim/theory.py`.
- **Figures:** F4 by `scripts/v2/31_fig_f4.py` (advantage vs rho_L with simultaneous CIs, per-seed dots, T3 overlay).
- **Code:** `vmsim/` at the freeze commit (tag `v2.0-rc1`). After it, bug fixes only, each logged in `CHANGES_AFTER_FREEZE.md`.
- **Console schema:** `vmmbench/schemas/vmconsole.schema.json`.
