# THEORY: when does budget-aware selection beat a threshold?

Week 17 (card 25-31 Jan 2027; written 4 Oct 2026, before any evaluation-seed run). Closed forms: `vmsim/theory.py`. Numerical check: `scripts/v2/theory_check.py` → `results/v2/theory_check.json`, `theory_grid.csv` (3,024 grid points), `theory_recheck.json`; figure `results/figures/v2_theory_check.pdf`.

The plan's target statements were written as targets, not results. Finding out which hold is part of the work. Two of them hold as stated (T1, T2). One holds in a sharper form (T3). One is partly false (T4), and the false part changes how the guard should be read.

## 1. Setup

One decision, made once, over a horizon H (30 days):
- **Items** i = 1..N are the VMs that may move. Each has a weight w_i (GB, the budgeted resource), an interruption cost c_i if its host fails while it is there, and a migration cost m_i.
- **Probabilities.** p_i is the probability that item i's host fails within H. e_i is the probability that a migration completes before that failure.
- **Expected benefit** of moving i: b_i = p_i c_i e_i − m_i. The budget allows Σ w_i ≤ B.
- **Expected cost** of moving a set S: C(S) = C_0 − Σ_{i∈S} b_i, where C_0 = Σ p_i c_i is the expected cost of moving nothing.
- **Policies.** P2 (threshold) ranks items by p and moves until the budget is used. BAM ranks by density b_i / w_i and moves while b_i > 0, within the budget.
- **Delta** = (C_P2 − C_BAM) / C_P2, the protocol's definition. Positive means BAM is better.

Assumptions:
- **A1, calibrated p:** P(host fails within H | what the policy knows) = p.
- **A2, failures given p:** failures are independent of everything else given p. Within a host, VMs share a fate. Expected-cost statements do not need independence; variance statements do.
- **A3, fixed budget** B in the budgeted resource (GB), the same for both policies.
- **A4, additive costs:** total cost = Σ interruption costs + Σ migration costs.
- **Accounting (`PROTOCOL.md` section 4, rule 1):** a migration is credited only if the source fails within the H the decision used. **T2 is a statement about this accounting.**
- **Fixed e (for T1):** e_i does not depend on which other items move. The simulator's queue-aware e breaks this (section 6).

For T3 and T4 only:
- **Equal weights:** w_i = w, so the budget is a share q of the items.
- **Proportional migration cost:** m_i = μ w_i, with λ = μ / E[p κ].
- **Gaussian copula:** X = log p and Y = log κ are bivariate normal with correlation ρ and SDs σ_x, σ_y (σ_logκ), where κ_i = c_i e_i / w_i is the averted-cost value per unit of weight.

## 2. Statements and their status

### T1. Density ranking is optimal for the stated budget (proved, standard)

With fixed e, choosing S is a 0/1 knapsack: maximise Σ b_i x_i subject to Σ w_i x_i ≤ B. Its LP relaxation (x_i ∈ [0, 1]) is solved by sorting on b_i / w_i and taking items with b_i > 0 until the budget is used, with the last item fractional (Dantzig 1957). The greedy integral solution, density order skipping items that do not fit, is within max_i b_i of the LP optimum, so within one item of the integer optimum.

BAM-GB is this greedy, with first-fit filling as the engine applies it. Queue-aware e makes the problem non-separable. The Week 15 exact check (`scripts/v2/18_bam_exact_check.py`, scipy MILP) measured BAM's gap on 200-VM simulator snapshots: mean 0.05%, 95th percentile ≤ 0.30%.

**C1** (corollary). Ranking by p alone is optimal for every budget only if κ is constant or comonotone with p, and the budget does not exceed the items with b > 0. P2's rule "use the budget" breaks the second condition whenever many items have b ≤ 0.

### T2. Delta ≥ 0 under A1-A4 (proved; checked numerically)

P2's selection is feasible for the knapsack, and BAM's greedy is within one item of its optimum. Therefore C_BAM ≤ C_P2 + max_i b_i⁺, so Delta ≥ −max_i b_i⁺ / C_P2. In the fractional (large-N) limit, Delta ≥ 0.

Numerical check: the smallest closed-form Delta over the 252 grid points with no noise and γ = 1 is +0.0006. The Monte Carlo has no point below 0 beyond its tolerance.

T2 needs calibrated p and the one-horizon accounting. It says nothing when either fails; v1 failed both (section 5).

### T3. Closed form under a Gaussian copula (derived; checked numerically)

Both rules select items {W > t} for a linear score W = aX + bY. P2 uses a = 1, b = 0. BAM uses a = b = 1 and stops at log μ. With Z = X + Y and M = E[pκ] = exp(μ_x + Var Z / 2), exponential tilting gives:

- E[e^Z 1{W > t}] = M Φ((m_W + Cov(Z, W) − t) / s_W)
- P(W > t) = Φ((m_W − t) / s_W)

When the budget binds for both rules (t is the 1 − q quantile), the two expected benefits per item, as shares of C_P0, differ by the **ranking term**:

Φ(z_q + σ_z) − Φ(z_q + σ_x + ρ σ_y),   with z_q = Φ⁻¹(q) and σ_z² = σ_x² + 2ρσ_xσ_y + σ_y².

- **The ranking term is never negative**, because σ_z² − (σ_x + ρσ_y)² = σ_y²(1 − ρ²) ≥ 0. It is zero if and only if σ_y = 0 or ρ = 1.
- **The stopping term:** BAM also gains whatever P2 loses by moving items with b ≤ 0, through t = max(t_q, log μ). This term grows with λ and with q.

Numerical check: all 3,024 grid points agree within the tolerance (section 4) once the 13 that first missed were rerun with 80 replicates (`theory_recheck.json`). Largest error after the rerun: 0.0006.

What T3 says about ρ, which matters for the paper:
- **The advantage of density over p-ranking is largest near ρ = 0 and falls to zero as ρ → 1.** At ρ = 1, critical VMs already sit on the riskiest hosts, so ranking by p already picks them. With free migration (λ = 0, q = 0.02, σ_logκ = 0.5), Delta is 0.6% at ρ = −0.9, 3.4% at 0, 2.7% at 0.5, 0.75% at 0.9 and 0.08% at 0.99.
- **The spread of κ, not ρ, sets the size.** At ρ = 0, q = 0.02, λ = 1, Delta is 0.13% at σ_logκ = 0.1, 0.8% at 0.25, 3.3% at 0.5 and 13.2% at 1.0.

v1 framed the question as "cost-awareness pays above a break-even correlation (ρ ≈ 0.3)". Under A1-A4, there is no such crossover. Cost-awareness never loses (T2), and its gain is driven by the cost spread and shrinks as ρ → ±1.

### T4. Noise and miscalibration (partly false as stated)

The plan's statement was: "Delta falls with σ_noise and a sign-flip threshold exists". Model: log p̂ = γ(X + σ_n ε) + log k, where k keeps the mean of p̂ when σ_n = 0.

1. **With γ = 1 and ρ ≥ 0, Delta never turns negative** (0 of 576 grid points). It is not monotone in noise: in 65% of these settings, moderate noise *raises* Delta before large noise lowers it. Noise hurts P2, which ranks by p alone, more than it hurts BAM. When ρ > 0, κ carries information about p, which BAM still uses. **"Delta falls with noise" is false at ρ ≥ 0.**
2. **A sign flip exists only for negatively aligned costs.** With the budget binding for both rules, BAM's ranking term turns negative above a noise level σ_n* if and only if σ_x² + ρσ_xσ_y > σ_z², that is ρ < −σ_y / σ_x (closed form in `theory.noise_flip`). Examples with σ_x = 1:
   - ρ = −0.6, σ_logκ = 0.5: σ_n* = 1.24;
   - ρ = −0.9, σ_logκ = 0.25: σ_n* = 0.18.

   Over the grid, γ = 1 gives a negative Delta at 112 of 432 points with ρ < 0, down to −9.4%.
3. **Flattening miscalibration (γ < 1) is the dangerous direction.** At γ = 0.5, Delta can be negative with no noise, and also at ρ ≥ 0 (13 of 576 points, down to −4.2%). BAM's stopping rule then compares a flattened p · κ with μ and mis-sizes its selection. Sharpening (γ = 2) is safe at ρ ≥ 0 (minimum +0.06%).

Consequences:
- **Calibration matters more than discrimination for BAM.** That is the case for P6's calibration audit, and for auditing the reliability slope rather than PR-AUC.
- **The direction of the drift is favourable.** The drift study found reliability slopes 0.76-0.97 (over-dispersed, γ ≈ 1 / slope > 1), the safe direction under T4.3. The ensemble's test slope of 1.16 is slightly under-dispersed (γ ≈ 0.86), the risky direction. Rolling recalibration or the audit covers it.

## 3. Break-even surface (task 4)

Where Delta crosses δ = 1% in (ρ, σ_logκ). Closed form, no noise, q = 0.02 (`theory_check.json`, `break_even_q002`):

| σ_logκ | λ = 0 or 1 | λ = 4 |
| --- | --- | --- |
| ≤ 0.25 | below 1% at every ρ | below 1% at every ρ |
| 0.5 | above 1% for ρ in (−0.82, 0.86) | above 1% for ρ < 0.85 |
| 0.75 | above 1% for ρ in (−0.93, 0.95) | above 1% for ρ < 0.94 |
| 1.0 | above 1% for ρ in (−0.98, 0.97) | above 1% for ρ < 0.97 |

**This replaces pH for interpretation only. It never re-classifies G1** (`PROTOCOL.md` section 7; G1 = C0 is final).

Read against G1: real placement sits at ρ ≈ 0 (C0). Under the one-shot theory, that is where cost-awareness gains most, provided costs are spread. The simulator's VMs have σ_logκ ≈ 1.06 (Azure sizes and v1's tier weights, `engine.kappa_reference`). So C0 does *not* mean "nothing to gain". It means the gain cannot come from critical VMs sitting on risky hosts, and must come from cost spread.

Whether the simulator shows this is the Week 18 question. Regimes A1-A7 sweep ρ and E1-E3 sweep σ_logκ at ρ = 0. The Week 15 finding (BAM as specified over-migrates, because one-shot b ignores the option to wait) predicts that the simulator will fall short of T3.

## 4. Tolerance (set now, before any evaluation run)

- **Theory internal check** (`PROTOCOL.md` claim 2, "Monte Carlo and the closed form disagree beyond the tolerance"): |Delta_MC − Delta_CF| ≤ max(3 SE, 0.001), with SE the jackknife over Monte Carlo replicates. 0.001 is a tenth of δ. A point that fails is rerun with 8× the replicates before it counts as a disagreement. Result: 3,024 of 3,024 agree.
- **Theory against the simulator (F4 overlay, Week 18):** no numeric tolerance is claimed. The simulator breaks the one-shot assumptions on purpose (section 6). The overlay shows the T3 curve at the simulator's measured σ_x, σ_logκ, λ and effective ρ, and the paper reports the gap and its sign. Agreement is judged on direction: Delta ≥ 0 at every ρ, largest near ρ = 0 and growing with σ_logκ. A simulated Delta below 0 in any A or E cell, beyond its CI, counts against T2's relevance, and is a bug-hunt first.

## 5. The v1 anomaly, closed

At ρ = 0, T2 predicts that cost-awareness does not lose. v1 reported −3.1%. The Week 3 diagnostics (`v1_anomaly.md`) show which assumptions v1 broke:
- **A3 (the same budget):** the threshold got 8% more hosts and 21% more GB (H3; about 2 of the 3.1 points);
- **the one-horizon accounting:** migrations were credited with failures a median 170 days later, while the decision used a 30-day p (H6; the rest).

With both repaired, v1 measured +0.19% (same GB) and +0.22% (exact count). T3 accounts for that size. At v1-like spreads (σ_logκ = 0.37-0.56 at host level, H4), with q = 5,116 / 122,618 = 4.2% and σ_x of 0.3 to 1, Delta is 3-6% of the **30-day** expected cost. In v1, the cost of the decision's 30-day window (Σp ≈ 237 expected failures) is about 3.4% of all 6,912 failures charged over the run. So T3 predicts about 0.1-0.2% of v1's total cost, in line with the measurement.

**In two sentences:** the threshold won at ρ = 0 because v1 gave it a larger budget and credited migrations with failures months after the 30-day decision, which breaks the two assumptions under which cost-aware selection cannot lose. With the budget matched and the accounting aligned to the decision horizon, the cost-aware rule is ahead by about 0.2%, which is what the closed form predicts once the gain is diluted by the share of v1's total cost that a 30-day decision can affect.

## 6. What the simulator adds (where the theory can fail)

- **Repeated decisions.** Decisions are made daily with a 30-day p. Moving today forgoes the option to wait, which b ignores (Week 15 finding).
- **VMs leave.** c is survival-weighted, but a migration still protects only the VMs present.
- **Destination risk.** A moved VM can fail on its destination. b assumes the destination is safe. Measured on 2 Nov 2026: this and repeated moves together collapse BAM once m is small against c, and charging it restores a positive saving (`RESULTS_SELECTIVE_NET.md`).
- **Queue-aware e.** Selection is no longer separable (T1 holds approximately; MILP gap 0.05%).
- **Budget per day, not per decision.** At a 2% daily budget BAM rarely binds (it used 4.6% of its budget in the Week 15 smoke). Its advantage over budget-tuned P2 then comes mostly from the stopping term (λ), not the ranking term.
- **Host-level failures.** All VMs on a host fail together. Expectations are unaffected; seed variance is not.
