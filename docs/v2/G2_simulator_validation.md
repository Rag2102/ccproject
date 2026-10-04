# Gate G2: can the simulator be trusted? (Week 13)

Status: **accepted** (owner with advisor, recorded 4 Oct 2026; ahead of the calendar, the card is 28 Dec 2026 to 3 Jan 2027). All five criteria of `PROTOCOL.md` section 7 are met on the evidence below. Tag `sim-v2.0`.

Code: `vmsim/` at f0b0df4 plus the Week 14 commit. Numbers: `results/v2/g2_validation.json` (`scripts/v2/15_g2_validation.py`), `results/v2/shape_check.json`, and the `tests/v2` suite.

## Table 4. Validation summary

| # | Criterion (PROTOCOL section 7) | Check | Result | Pass |
| --- | --- | --- | --- | --- |
| 1 | Analytic degenerate cases | 20,000 hosts, constant hazard 0.01/day, one static VM each, 30 days; 5 seeds per case. Never migrate: interruptions vs N·p_T (p_T = 0.260, expected 5,206). Move every VM at day 0: same expectation, because under a memoryless hazard a migration is pure cost (cancelled migrations included) | Never: z = 0.10, −1.29, 0.44, −0.92, 2.61. Move all: z = 0.76, −2.24, −0.06, −0.23, 2.10. Also exact: P0's cost equals c × (hosts failing within T) on every seed | Yes |
| 2 | Self-calibration | 1,000 hosts × 3 seeds, days 60, 150 and 240: failures in the next 30 days of hosts up at day d, against the sum of the oracle's p_H, **across repairs** (renewal hazard) | 109 observed vs 111.9 expected (z = −0.28); largest decile \|z\| = 0.93 | Yes |
| 3 | v1 regression within 1% | v1's setting (2,013,767 static VMs on 122,618 one-drive hosts, v1's random draw, 30-day per-host decisions) computed with vmsim's migration model (v1 closed form), cost model, P3 urgency and realised-cost accounting | Cost-sensitive 456,532.7 vs 456,533 (5,116 migrations, exact). Threshold at matched budget 442,700.7 vs 442,701 (5,522, exact). Relative differences −6 × 10⁻⁷. Naive threshold 410,867 also reproduced | Yes |
| 4 | Invariants and determinism | `hypothesis` over seeds, the five reference policies, budgets {0, 0.5, 2, 20}%, random and adversarial placement, non-disk 0× and 3×, every day checked: VM conservation, memory accounting exact and within capacity, monotone time, no migration to a down host, budget never exceeded. Plus: byte-identical outcomes for identical inputs, CRN across policies, zero budget gives P0's outcomes for every policy, tie order (a failure at a migration's end instant interrupts the VM; a destination failure then cancels it without an interruption), self-calibration across repairs | All pass (`tests/v2`, 91 tests in the repo suite) | Yes |
| 5 | Run time | One (policy, seed) run, 5,000 hosts × 365 days + 30 warm-up, one core, Apple silicon. Target ≤ 10 s (SIM_SPEC section 13) | P0 2.0 s, P1 3.5 s, P3 2.2 s, P7 2.2 s, P8 4.8 s (549k migrations). v1 scale (122,618 hosts, 30 + 30 days): 12.7-18.4 s and 7.3 GB peak | Yes |

Also recorded (SIM_SPEC section 14, check 5, shape only): per-node uptime between failures has Weibull shape 0.94 (1× non-disk) and 0.98 (3×). Node logs are reported with a decreasing hazard (shape about 0.7-0.8, Schroeder and Gibson 2006; **to verify against the paper**). The simulator's per-node hazard therefore decreases less than real nodes'. This is a known limitation, not a gate criterion.

## What criterion 3 does and does not test

The regression runs v1's setting through the simulator's **components**: the migration model, the cost model, the policy rules and the accounting. It does not run it through the event loop. v1's hosts each run on their own age clock over up to five years, which the engine's shared calendar does not represent.

The event loop is validated separately: by the analytic cases (1), self-calibration (2) and the invariants (4).

With static VMs, realised-cost accounting is exactly v1's accounting: a VM moved off a host that fails later is safe, because it never leaves its new host and nothing arrives on the old one. The intended difference from v1 is therefore not an accounting mode but **VM churn**. In the v2 engine VMs arrive and leave, so a migration protects only the VMs present, and only while they would have run (PROTOCOL section 4, rules 1 and 2).

## Design changes made while building, for the record

These are in `SIM_SPEC.md` v0.2. None changes a protocol rule; items 1 and 2 change how the spec's model is computed.

1. **Day-stepped with exact times, not one event heap.** An event per VM would mean about 16 million arrivals per run (median Azure VM lifetime 40 minutes) and would miss the 10 s target by an order of magnitude. Each day is a batch; failures, migrations, arrivals and departures are resolved at their exact times within it. Memory of departed VMs is freed at the next tick, so capacity is never over-committed.
2. **Residents and transients.** VMs living at least a day are simulated individually: 12% of VMs, 92% of memory-time. Shorter ones are charged at each host failure as a Poisson draw from the failure stream. No policy may migrate a VM younger than 24 hours, so a policy's view is exactly what a real operator would see, and transients cost every policy the same.
3. **Budget rule.** The engine fills the budget in each policy's order, skipping any VM that no longer fits (PROTOCOL: "to within one VM, filling the remainder in its declared order").
4. **Destinations.** Power of two choices for every policy. The policy may rank the two candidates; all use p_H except the oracle, which takes the candidate that fails later.
5. **Common random numbers in placement.** Each arrival has a pre-drawn uniform for its first-choice host, and the per-day generators are keyed by day. A difference between two policies on one day therefore does not shift later draws.

## Open items at sign-off

- The node-log shape value (0.7-0.8) is from memory of Schroeder and Gibson (2006) and must be checked against the paper. Not a gate criterion: it affects only the limitation's wording.
- Done 4 Oct: owner and advisor acceptance; tag `sim-v2.0`.
