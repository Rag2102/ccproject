# Simulator v2: design specification (Week 10)

Status: v0.1, 4 Oct 2026 (ahead of the calendar); the three open defaults were confirmed by the owner on 4 Oct. Source: v5 plan Part I section 7 (architecture, parameters, validation), v3 section 3.1 (BAM), `PROTOCOL.md` v0.2 (policies, regimes, accounting), v1's code for the regression values. The test for this document (Week 10 card): someone can implement from it without asking a question. Items left open are listed in section 15.

## 1. What the simulator must do

- Replay a cluster of hosts for T days, with VMs arriving and leaving, hosts failing, and a policy migrating VMs under a daily budget, and report the cost of everything that actually happened.
- Give every policy the **same failures and the same VM arrivals** for a given seed (common random numbers), so all comparisons are paired.
- Reproduce v1's headline numbers within 1% under v1 settings (gate G2, criterion 3), and fix v1's accounting by construction. Cost is what actually happens: an interruption is charged only when a host fails while a VM is on it. There is no counterfactual "averted failure" credit, so the Week 3 asymmetry cannot occur.

## 2. Time model

- Time t is in seconds from the start of the run, stored as float64; day d = floor(t / 86,400).
- **Hybrid.** At the start of each day a SCORE_TICK scores every host at once (vectorised). Within the day, a heap of timed events (failures, migration ends, VM arrivals and departures) is processed in time order.
- **Tie order** at equal t: HOST_FAIL, then MIG_END, VM_DEPART, VM_ARRIVE, MIG_START. A failure at the same instant as a migration end therefore interrupts the VM: the conservative choice, and the one a property test checks.
- Horizon T ∈ {180, 365} days plus a 30-day warm-up whose costs are not counted (it fills the cluster to its steady state).

## 3. Entities (structure of arrays, NumPy)

| Entity | Fields | Notes |
| --- | --- | --- |
| Host | `id`, `state` (UP, AVOID, DOWN), `cap_gb`, `used_gb`, `nic_gbps`, `n_active_mig`, `drives[d]` (indices), `fail_t` (pre-drawn), `repair_t`, `rack` | AVOID = no new allocations. DOWN from failure until repair; on repair the host returns empty, with new drives (age 0) |
| Drive | `id`, `host`, `model`, `cap_tb`, `age0_days`, `fail_t` (or +inf), `source_serial` | Replayed: a real Backblaze drive (life table + daily scores) re-timed onto the run's clock. Sampled: drawn from the hazard model |
| VM | `id`, `host`, `state` (RUNNING, MIGRATING, DONE, INTERRUPTED), `mem_gb`, `vcores`, `tier`, `w_tier`, `dirty_mbps`, `t_arrive`, `t_depart`, `crit_latent` | `t_depart` is pre-drawn from the lifetime distribution, so it is the same for every policy |
| Migration | `vm`, `src`, `dst`, `t_start`, `t_end`, `gb`, `blackout_s`, `status` (RUNNING, DONE, FAILED) | FAILED = the source failed before `t_end`: the VM is interrupted |
| Event | heap of (t, kind, payload), with kind order as in section 2 | `HOST_FAIL`, `SCORE_TICK`, `MIG_START`, `MIG_END`, `VM_ARRIVE`, `VM_DEPART`, plus `HOST_REPAIR` |

## 4. Event types and state transitions

| Event | Effect |
| --- | --- |
| `SCORE_TICK(d)` | Predictor scores every UP or AVOID host, giving (p_H, E_TTF, p per interval). The policy returns a plan: a list of (vm, dst) migrations within today's budget, plus AVOID flags. Migrations become `MIG_START` events, queued per source host (at most `max_concurrent_mig` at once) |
| `MIG_START(vm, src, dst)` | Requires src and dst UP or AVOID, dst capacity ≥ mem, the VM RUNNING and not yet departed (otherwise the migration is dropped and its budget refunded). Reserves memory on dst. VM → MIGRATING. Schedules `MIG_END` at t + duration (section 6) |
| `MIG_END` | VM → RUNNING on dst; frees src memory; charges the migration cost; starts the next queued migration on src |
| `HOST_FAIL(h)` | Host → DOWN. Every RUNNING or MIGRATING VM on h, and every VM migrating **from** h, becomes INTERRUPTED and is charged its interruption cost. A migration **to** h is cancelled: the VM stays on its source, the GB already moved counts against the budget, and no interruption is charged. Schedules `HOST_REPAIR` at t + repair time |
| `HOST_REPAIR(h)` | Host → UP, empty, with new drives (age 0) and a newly pre-drawn `fail_t` from the host's own stream (section 7) |
| `VM_ARRIVE` | Placement (section 8) picks an UP host (never AVOID or DOWN) with capacity. If none has room, the arrival is rejected and counted (a validity metric, not a cost) |
| `VM_DEPART` | VM → DONE; frees memory; a queued or running migration of it is cancelled (GB already moved still counts) |

**Interrupted VMs are not restarted** in the run. Their remaining lifetime is lost, which is what the interruption cost stands for.

## 5. Accounting (units)

All costs are in customer-impact minutes (v1's unit), split into two reported components.

| Item | Formula | v1 value (regression) |
| --- | --- | --- |
| Interruption cost of VM i | c_i = w_tier(i) × D_fail | D_fail = 10 min; w = 1.0 / 0.6 / 0.3 (high / medium / low) |
| Migration cost of VM i | m_i = m_customer + λ_bw × m_resource, with m_customer = w_tier × blackout_s / 60 and m_resource = duration_s / 60 | λ_bw = 1 (v1 adds both); blackout 1 s if pre-copy converges, else 60 s |
| Total cost (primary metric) | Σ c_i over interrupted VMs + Σ m_i over completed or failed migrations | |
| Necessary migration | The source fails within H days of the migration's start **and** the VM would still have been running at that failure (t_depart > fail_t) | Metric only; not a credit |
| Unnecessary migration | Every other completed migration | Metric only |
| Failed in-flight migration | Interruption cost and migration cost both charged | |

The **budget** is GB migrated per cluster per day: B = b × (cluster memory), with b ∈ {0.5, 1, 2, 5}%. A migration's GB is charged when it starts. A run that exceeds the budget on any day is invalid (property test). Counts are reported next to GB.

## 6. Migration model

Pre-copy, in the spirit of Clark et al. (2005) and following v1's formulas where they exist:

- Usable bandwidth: bw = nic_gbps × usable_share × 125 MB/s per Gbps, shared equally by the host's concurrent migrations (default 10 Gbps × 50% = 625 MB/s; v1 used 1,250 MB/s and no sharing, so the regression run sets usable_share = 1 and max_concurrent = ∞).
- Dirty rate: dirty = (avg_cpu / 100) × 150 MB/s (v1).
- Rounds: round 0 sends all memory, and round k sends what was dirtied during round k − 1. Stop when the remainder is ≤ 50 MB (stop-and-copy, blackout = remainder / bw, at least 1 s as in v1) or after 30 rounds (forced stop-and-copy of the remainder). If dirty ≥ 0.9 × bw, it does not converge: fallback blackout of 60 s (v1).
- Duration = Σ round times + blackout. GB moved = memory + Σ re-sent pages (the budget charges the memory only, as the plan defines GB migrated; total bytes are reported separately).

The regression run uses v1's closed form instead of the rounds (duration = mem / (bw − dirty); blackout 1 s or 60 s), so v1's numbers can be matched exactly.

## 7. Failure process and common random numbers

- **Drives.** Each host has d ∈ {1, 4, 12} drives (swept). Drive slots are filled by drawing real drives from the Backblaze life table with their model, capacity, starting age and observed outcome (failure day or censoring). Their daily scores come from the v2 model on their real SMART history. A drive censored before the run ends is extended with a failure time drawn from the model's hazard given survival to censoring.
- **Non-disk causes.** h_other is Weibull with shape 0.7 (< 1, an explicit assumption) and scale set so that non-disk failures are as likely as disk failures over a year (1×). It is swept at 0×, 1× and 3×.
- **Host failure time** = min(drive failure times, non-disk failure time). Host hazard = 1 − Π(1 − h_drive) × (1 − h_other).
- **Pre-drawn.** All failure times are drawn once per seed, before any policy runs, from the `failures` stream. Policies cannot change when hosts fail; they can only move VMs off them.
- **Repairs.** Repair time is lognormal with median 2 days (assumption, swept). A repaired host draws its next failure from `failures.spawn(host, k)` for its k-th life, which is still identical across policies.
- **Correlated shocks (stretch, regimes R1-R3):** a rack-level Poisson shock fails a share of the hosts in the rack at once.

**RNG streams.** `root = SeedSequence(seed)`; children, in order: `failures`, `placement`, `arrivals`, `lifetimes`, `predictor`, `policy`. Arrivals and lifetimes are pre-drawn as arrays (arrival times, sizes, tiers, lifetimes, latent criticality). Placement uses one pre-drawn uniform per arrival, so two policies make different placements only where the cluster state differs. The **CRN contract**, which a property test checks: for the same seed, every policy sees identical host failure times (first life) and identical VM arrival sequences.

## 8. Placement (the regimes)

At each arrival, choose among UP hosts with capacity:

| Regime | Rule |
| --- | --- |
| A1-A7 | Latent Gaussian copula. The VM's latent criticality z_v (drawn with its tier; the tier is the quantile of z_v) and each host's risk latent z_h (the normal score of its current p_H rank) give a score s = ρ_L·z_v·z_h + noise. The VM goes to argmax s over 32 random candidate hosts with capacity. This reproduces random placement at ρ_L = 0. ρ_L is calibrated against the achieved τ-b in Week 11 |
| B1 | Rank copula at the measured ρ̂ (CI low, point, high from Week 8) with measured dispersion |
| B2 | Class-conditional: tier drawn given the host's class, using the measured tier mix per class |
| C | Adversarial: critical VMs to the riskiest hosts with room |
| D | ρ_L moves from 0.1 to 0.6 at mid-run; calibration drifts (γ from 1.0 to 0.7) |
| E1-E3 | ρ_L = 0; σ_log κ ∈ {0.25, 0.5, 1.0} |

**Initial fill (confirmed 4 Oct):** the warm-up fills the cluster to 70% memory with the same placement rule.

## 9. Predictor interface

`score(hosts, t) -> (p_H, E_TTF, p_interval)` for every host, with four implementations:

- **oracle:** the true conditional probability under the generator (computed from the drives' known hazards and the Weibull);
- **noisy(σ):** logit(p) + N(0, σ²), with a per-host-per-day draw from the `predictor` stream;
- **model:** the calibrated v2 model's daily score for each replayed drive, combined across the host's drives;
- **miscal(γ):** p′ = p^γ, rescaled so the mean over hosts is unchanged (the plan's Week 12 definition; γ < 1 flattens the risk ranking, γ > 1 sharpens it).

## 10. Policy interface

`plan(state, scores, budget_gb, rng) -> (migrations[(vm, dst)], avoid_flags)`. Policies P0-P8 as in `PROTOCOL.md` section 2.

**BAM terms, per VM i on host j:**
- b_i = p_j · c_i · e_i − m_i, with w_i = mem_gb;
- e_i is the probability that the migration finishes before the host fails, given its position in the host's queue (from E_TTF and the duration of the migrations ahead of it); it is recomputed after each pick.

**VM lifetimes (confirmed 4 Oct).** The median Azure VM lives 40 minutes (`v1_anomaly.md`, H6). Most VMs on a host will leave before it fails, which the plan's c_i does not account for.
- **Default:** BAM and P3 use c_i × s_i, where s_i is the probability that VM i is still running H days ahead given its current age, from the empirical Azure lifetime distribution. A policy may know a VM's age; it may not know `t_depart`.
- Both versions are run as an ablation in Week 20.

**Destination:** power of two choices. Draw two random UP hosts with capacity and pick the one with lower p_H.

## 11. Parameters

| Parameter | Default | Source | Swept in Week 20 |
| --- | --- | --- | --- |
| Risk horizon H | 30 days (also 7, 14) | v1 step; `label_spec.md` | 7, 14, 30 |
| Scoring cadence | daily | plan section 7.2; Narya scores periodically (to verify against the paper) | — |
| Hosts per cluster | 2,000-5,000 (set by the Week 14 pilot) | plan; power from seeds, not scale | — |
| Drives per host d | 1, 4, 12 | plan; Week 4 group columns give real pod sizes | 1, 4, 12 |
| VMs per host | about 16 on average | v1: 2.01M VMs on 122,618 hosts | ±50% |
| Host memory | 144 GB | 16 VMs × 6.07 GB mean (Azure V1; largest VM 112 GB) ÷ 0.70 fill | with VMs per host |
| VM size, CPU, tier, lifetime | resampled jointly from Azure V1 (`azure_vms_clean.csv.gz`) | v1 | tier weights: 3 alternative vectors |
| NIC bandwidth, usable share | 10 Gbps, 50% | assumption (v1: 1,250 MB/s, 100%) | 25%, 50%, 100% |
| Concurrent migrations per host | 2 | assumption | 1, 2, 4 |
| Pre-copy rounds, stop threshold | max 30, 50 MB | Clark et al. 2005 (to verify) | — |
| Dirty rate at 100% CPU | 150 MB/s | v1 | ±50% |
| Unmitigated downtime D_fail | 10 min | v1 | ±50% |
| Blackout (converged / fallback) | 1 s / 60 s | v1 | — |
| Tier weights | 1.0 / 0.6 / 0.3 | v1 | 3 alternatives |
| Non-disk hazard | Weibull, shape 0.7, scale for 1× disk | assumption | 0×, 1×, 3× |
| Repair time | lognormal, median 2 days, σ = 0.5 | assumption | ×0.5, ×2 |
| Budget | 0.5, 1, 2, 5% of cluster memory per day, in GB | plan | all four |
| Horizon T | 180 or 365 days + 30 warm-up | plan | — |

## 12. Invariants (property tests, `hypothesis`)

1. **VM conservation:** RUNNING + MIGRATING + DONE + INTERRUPTED = arrived, at every event.
2. **No capacity violation:** used_gb (including reservations) ≤ cap_gb on every host at every event.
3. **Monotone time:** event times never decrease.
4. **Determinism:** byte-identical output for identical (seed, policy, regime, parameters).
5. **No migration to a DOWN host,** and none to an AVOID host.
6. **Budget:** GB started per day ≤ budget + one VM (the exact-budget rule).
7. **CRN:** for a seed, failure times (first life) and arrival arrays are identical across policies.
8. **Zero-budget equivalence:** with b = 0, every policy's output equals P0's.
9. **Oracle bounds:** with the oracle predictor, P7 ≤ every policy in cost, and P7's cost is non-increasing in budget.

## 13. Architecture and performance target

- Package `vmsim/` (plan Part I section 6): `config.py`, `rng.py`, `entities.py` (structure of arrays), `placement.py`, `failure.py`, `predictor.py`, `migration.py`, `accounting.py`, `engine.py` (event heap), `policies/`. The policies are pure functions of (state view, scores, budget, rng).
- Daily scoring is vectorised over hosts. The per-VM loop runs only inside a policy's plan, over hosts with p above a floor, and inside the event loop.
- **Performance target, checked in Week 13:** one (policy, seed) run of 5,000 hosts × 365 days in **≤ 10 s on one core** of this Mac. The main matrix is about 16,000 such runs (n ≈ 30 seeds × about 15 regime cells × 4 budgets × 9 policies), about 45 core-hours, or about 6 hours on 8 cores. If the target is missed, the cut order is R3's: shrink hosts before cutting seeds.

## 14. Validation (gate G2)

1. **Analytic:** one host, one VM, known p, known costs; expected cost matches the closed form within Monte Carlo error (10⁵ seeds).
2. **Self-calibration:** over 1,000 hosts, simulated 30-day failure counts match Σ p_H within a binomial 99% interval, per decile of p.
3. **v1 regression:** v1 settings (static VMs, no departures, v1 migration formulas, random placement, host = one drive, v1's per-host decision) reproduce 442,701 and 456,533 within 1%.
4. **Invariants and determinism:** section 12.
5. **Shape check:** simulated host inter-failure times compared with LANL node logs (shape only).
   - **First record** (4 Oct, `scripts/v2/14_shape_check.py`, `results/v2/shape_check.json`; 2,000 hosts, seeds 1-5, first lives only, v1 hazard source):
     - cluster-wide gaps between failures fit a Weibull shape of 0.99-1.03 (coefficient of variation 0.96-1.06), close to exponential, as expected for many independent hosts pooled together;
     - time to a host's first failure has shape 1.5-1.7 (rising hazard, from v1's age curves);
     - 0.09, 0.14 and 0.23 failures per host-year at 0×, 1× and 3× non-disk hazard.
   - **Still to do:** the comparison with node logs needs per-node times between failures, so repaired hosts must fail again. That arrives with the Week 13 engine.
6. **Run time:** section 13.

## 15. Open items

- Confirmed 4 Oct: survival-weighted c_i in BAM and P3, with the unweighted version as an ablation; initial fill 70%; a repaired host returns empty with new drives.
- To verify against sources: Narya's scoring cadence; Clark et al.'s round and stop thresholds.
- Week 11 calibrates the A-regime placement's ρ_L to the achieved τ-b, using the same contingency code as `scripts/v2/13_trace_rho.py`.

Reader test (Week 10 card): ask someone to read this for 30 minutes and list every question they would have to ask before implementing. Each question is an edit to this file.
