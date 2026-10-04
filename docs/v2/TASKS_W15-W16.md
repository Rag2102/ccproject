# Tasks, Weeks 15-16

From the v5 week cards for W15 and W16 (plan page 18). Built on 4 Oct 2026, ahead of the calendar (W15 starts 11 Jan 2027). `[x]` = done and checked; `[~]` = done, needs you; `[ ]` = not done.

## Week 15 (11-17 Jan): BAM-GB, its variants, and the Narya-inspired baseline

- [x] **P4, BAM-GB** (`vmsim/policies/bam.py`): b = p·c·e − m with survival-weighted c, queue-aware e recomputed after each pick (lazy heap; identical to a brute-force greedy on 40 random instances), w = GB, fill while b > 0; the engine reserves destination capacity as it goes
- [x] Variants: BAM-time (w = NIC-seconds), BAM-cost (w = m, ablation only)
- [x] Exact check (`scripts/v2/18_bam_exact_check.py`, scipy MILP/HiGHS; no new dependency): simulator snapshots of 200 VMs, gap mean 0.05%, p95 ≤ 0.30%, max 1.1%, 68% exactly optimal; synthetic, mean 0.19%, max 22% on one pathological instance (`results/v2/bam_exact_check.json`)
- [x] Ablation flags: `urgency=False` (e = 1), `c_uniform` (no criticality), `m_uniform` (uniform migration cost), `p_only`, `survival=False`
- [x] Identity test: p-only BAM with uniform c and m and no urgency equals P2 (tau = m / c) decision for decision, in three regimes and three within-host orders
- [x] **P5, Narya-inspired** (`vmsim/policies/narya.py`): simple (v5 spec: {nothing, migrate, avoid}, Beta posteriors, risk buckets) and faithful (NoOp / UA / UA-LM, Gamma-Poisson on cost, decay 0.99, 10% exploration, 14-day window); sticky per host; delayed, censored feedback from the engine's daily `Feedback`
- [x] `docs/v2/narya_differences.md`: every difference, row by row
- [x] Behaviour smoke (`scripts/v2/19_behaviour_smoke.py`, seeds 101-105, A3, 2%): BAM uses 4.6% of the budget (about 109 migrations a day; b > 0, not the budget, limits it); P5 2.1%; P5-faithful 0.7%, no migration on 46% of days, rejected arrivals doubled by avoid-allocation. Not the winner, by design
- [x] Engine: avoid-allocation marks, daily feedback, per-run `reset()` for stateful policies
- [~] **Finding for the theory (Week 17):** on single smoke worlds BAM migrates far more than the oracle and can cost more than never migrating. b = p·c·e − m treats today as the only chance to act with a 30-day p, but decisions recur daily and most VMs leave before their host fails, so waiting has value the formula ignores. It also ignores the destination's risk. BAM is implemented as specified; this is input to THEORY.md's assumptions, not a change to P4.

## Week 16 (18-24 Jan): uncertainty, drift, and P6

- [ ] Uncertainty on p: bootstrap ensemble of about 20 models; p_interval
- [ ] Drift study: train on years ≤ Y, test Y+1 and Y+2; ECE, slope, PR-AUC; rolling recalibration
- [ ] P6 plug-in advantage with a host-level bootstrap CI
- [ ] P6 calibration audit on matured outcomes
- [ ] P6 sequential validity (alpha spent across weekly looks)
- [ ] P6 switch rule with hysteresis, every switch logged
- [ ] Regret; regime D generator (rho_L 0.1 → 0.6 mid-run, calibration drift) unit-tested; P6 smoke on D (5 seeds) and on a pure-noise control
