# Protocol v0 (4 Oct 2026; tag `protocol-v0`)

This protocol fixes every decision rule before any v2 data is seen. Version 0 is the draft sent to the advisor in Week 3. Version 1.0 is frozen in Week 17 (tags `protocol-v1.0` and `v2.0-rc1`); after that, every change goes to `CHANGES_AFTER_FREEZE.md` and its results are exploratory.

Sources: v5 plan Part I sections 1-5, the week cards for W3, W14-W17 and W21, and the gate table carried over from v3 section 3.3. Where this file adds a rule, it says so and gives the reason. Items still open are marked **[set in Wn]** with the week that fixes them.

## 1. Claims and what would falsify them

Copied from `docs/v2/FALSIFICATION.md` (Week 2). Numeric tolerances are set where marked.

| Claim | Falsified if |
| --- | --- |
| 1. Real placement is at or above the break-even correlation (RQ1, C1) | The 95% CI of the measured correlation lies below pH = 0.30 in Google 2019 and in the second source, under every proxy and mapping (G1 class C) |
| 2. Under the stated assumptions, BAM-GB is never worse than a tuned threshold (RQ2, C2, C3) | In any cell meeting assumptions A1-A4, the Holm-adjusted upper bound of Delta vs P2 is below 0; or Monte Carlo and the closed form disagree beyond the tolerance **[set in W17]** |
| 3. The guard P6 makes the policy safe (RQ4, C3) | In any confirmatory regime, including D and a pure-noise control, the lower bound of P6's Delta vs P2 is below -1% at n >= 30; or P6 switches on the pure-noise control |

Week 3 evidence bearing on claim 2: in v1's simulator with calibrated synthetic p and 30-day accounting, the v1 rule (BAM at its own operating point) was ahead of the threshold on 10 of 10 seeds (`docs/v2/v1_anomaly.md`, H5). Under v1's original accounting it was behind on all 10. That is why section 4 fixes the accounting.

## 2. Policies

| ID | Policy | Role |
| --- | --- | --- |
| P0 | Never migrate | Floor for "benefit captured" |
| P1 | Fixed threshold tau = 0.0073 (v1's 95th percentile) | v1 continuity |
| P2 | Tuned threshold: best of three within-host orders (smallest-first, largest-first, random), tau tuned by bisection on dev seeds 101-110 to use the budget | **The comparator for every Delta** |
| P3 | v1 cost-sensitive rule (p * F * urgency > M) | v1 continuity |
| P4 | BAM-GB: for each VM b = p * c * e - m and w = GB; rank by b / w; fill while b > 0 and budget remains; recompute e for the host's queue after each pick | **Primary method** |
| P4-time, P4-cost | BAM with w = NIC-seconds, or w = m (the v2 rule) | Ablations only |
| P5 | Narya-inspired: actions {nothing, live-migrate, avoid-allocation}, risk buckets, Thompson sampling; differences from the paper listed in `narya_differences.md` (W15) | Strongest fair competitor |
| P6 | Safe-adaptive guard: BAM only when the CI lower bound of its plug-in Delta over P2 is > 0 and the calibration audit passes on two consecutive looks; otherwise P2 | Method (RQ4) |
| P7 | Oracle | Ceiling for "benefit captured" |
| P8 | Random selection within the budget | Sanity floor |

Rules added from the Week 3 diagnosis (`v1_anomaly.md`):

- **Exact budget.** Every policy, P2 included, spends the budget in the budgeted resource (GB) to within one VM, filling the remainder in its declared within-host order. v1's bisection missed the count by 8%, which was worth about 1 point of Delta.
- **Budget use is reported.** Any run that leaves more than 5% of its budget unspent (for example BAM stopping at b <= 0) reports the unspent share next to Delta. This is a rule I propose; confirm it.
- **Sanity checks (W14).** With zero budget, every policy equals P0. The oracle is never worse than any policy, and its cost does not increase with budget. P8 is never better than P2 in expectation (checked on 10 seeds). Under uniform c and m with no urgency, `--p-only` BAM equals P2 decision for decision.

## 3. Regimes, budgets and design

| ID | Placement | Parameters | Use |
| --- | --- | --- | --- |
| A1-A7 | Synthetic latent Gaussian copula | rho_L in {0, .15, .3, .45, .6, .75, .9}; sigma_log_kappa = 0.5 | Advantage curve; theory check |
| B1 | Rank copula calibrated on measured rho and dispersion | rho at CI low, point, high | Realistic regime (confirmatory) |
| B2 | Class-conditional replay | Tier given host class, as measured | Second realistic variant (confirmatory) |
| C | Adversarial | Critical VMs on the riskiest hosts | Upper range of benefit (confirmatory) |
| D | Non-stationary | rho_L 0.1 to 0.6 mid-run; calibration drift | P6, adaptive track |
| E1-E3 | Heterogeneity only | rho_L = 0; sigma_log_kappa in {0.25, 0.5, 1.0} | Isolates cost spread; explains v1 at rho = 0 |
| G, R1-R3, M | Extension (v4) | Measured costs; rack shocks; two budgets | Paper B; not part of this protocol's confirmatory family |

Budgets: 0.5, 1, 2 and 5% of cluster memory per day. Horizon T in {180, 365} days, drives per host d in {1, 4, 12} and hosts per cluster are **[set in W14]** by the power pilot and recorded in each scenario card.

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
- **Confirmatory family.** 30 comparisons: {P4, P5, P6} x {A3, A5, B1, B2, C} x {1%, 2%} budgets, each against P2. Holm correction on Wilcoxon signed-rank p-values for decisions; Bonferroni-simultaneous BCa 95% intervals for plots. Everything else is exploratory and labelled.
- **Variance reduction (pre-specified).** Common random numbers, a longer horizon, and regression adjustment of Delta on the realised failure count. Raw and adjusted Delta are both reported; the decision uses the adjusted one. This choice is added here; confirm it.
- **Display.** No bare means: every estimate has an interval, n and its family. At least one figure shows per-seed dots. Negative and null results are reported.
- **Seed families, never mixed.** dev 101-110 (tuning P2's tau and within-host order, P6's audit band, any submitted policy); pilot 201-205 (Week 14 only, then discarded); eval 1-n (n >= 30, set by the pilot); replication 1001 to 1000 + n; hidden 9001-9100 (leaderboard only; only a SHA-256 commitment is published). The Week 3 diagnostics used dev seeds only.
- **Protocol failures.** A crashed seed or invariant violation is handled by a rule written in Week 17; no seed is ever dropped for looking bad.

## 6. Power plan

The lower bound clears 0 for a true mean Delta of 1% only if the SD of Delta across seeds is below these values:

| Seeds | Max SD, uncorrected | Max SD, Bonferroni over 30 |
| --- | --- | --- |
| 30 | 2.7% | 1.6% |
| 50 | 3.5% | 2.1% |
| 100 | 5.0% | 3.1% |

Rule: the Week 14 pilot (seeds 201-205, cells A3 and B1 at 2%) measures SD(Delta) of P3 vs P2 as a proxy, and chooses n, hosts and horizon to meet the Bonferroni column. delta never moves; if the bound cannot be met, the design changes (longer horizon, more hosts), not delta.

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

- `protocol-v0` (this file): sent to the advisor in Week 3.
- `protocol-v1.0`: frozen in Week 17 with the matrix, n from the pilot, budgets, ablations, robustness and sensitivity grids, confirmatory family, analysis scripts and Console schema.
- After the freeze: `CHANGES_AFTER_FREEZE.md`; results produced under a change are exploratory.
