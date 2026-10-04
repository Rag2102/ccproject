# P5 and Narya: every difference (Week 15)

P5 is **Narya-inspired**, not a re-implementation. Narya (Levy et al., OSDI 2020) runs on Azure's proprietary telemetry with unpublished rules and thresholds, and reports results only as relative percentages. Source for the right-hand column: `reading/levy2020narya.md` (the Microsoft technical report, pages 1-16; numbers to be re-checked against the OSDI text before they are quoted). Code: `vmsim/policies/narya.py`; tests: `tests/v2/test_vmsim_narya.py`.

Two variants are kept, as the plan asks:
- **P5 (simple)** follows the plan's v5 wording.
- **P5-faithful** moves each choice towards the paper where the simulator allows it.

| Aspect | Narya (paper) | P5 simple (v5 spec) | P5-faithful |
| --- | --- | --- | --- |
| What flags a node | 51 hand-written rules plus a gradient-boosted model on 2,000+ features, cut-off 0.5, 7-day horizon | Host p_H in the top 2% of up hosts that day (the predictor under test) | Same as simple |
| Unit of decision | (node, prediction rule) | Host | Host |
| Context | Prediction rule / experiment; one model per experiment; contextual bandit is future work | Risk bucket: thirds of the flagged hosts by p_H | Same as simple |
| Actions | Primitive (Avoid, Unallocatable, Live Migration, Service Healing, Soft Reboot, Human Investigate) and composite (UA-LM-HI, UA-SR, UA-LM-RH, Avoid-RH), plus NoOp | {nothing, migrate, avoid} | {NoOp, UA, UA-LM}: unallocatable, and unallocatable then live-migrate. Reboot, service healing and human investigation have no counterpart in the simulator |
| Reward | Count of VM interruptions (cost) on the node, plus on nodes that received its migrated VMs, over 10-30 days | Binary "no interruption on the host during the window" | Cost in minutes over the window: interruptions on the host plus the migration cost charged for it. Interruptions of moved VMs on their destinations are **not** attributed back (the engine's feedback is per host) |
| Posterior | Gamma prior on a Poisson rate; choose the lowest sampled cost | Beta(1, 1) per (bucket, action); choose the highest sampled success | Gamma(1, 0.1) on the Poisson rate of cost minutes per episode; lowest sampled rate |
| Forgetting | Exponential decay, 0.99 | None | 0.99 per update |
| Exploration | Minimum and maximum action probabilities: 10% below 100 flagged nodes a day, 5% above | Thompson sampling only | Uniformly random action with probability 10% |
| Stickiness | Hash of node and experiment fixes the group | One action per host per episode | Same as simple |
| Observation window | 10-30 days | H = 30 days | 14 days |
| Evaluation | Inverse propensity scoring, to evaluate only | None inside the policy; the simulator measures realised cost | Same |
| Safety | Safety constraints and rate limits before applying an action | The engine's GB budget and capacity checks | Same |
| Migration cost and VM size | Not in the decision (VM size named as a factor in outcomes) | Not in the decision; the budget limits GB | Migration cost enters the reward, not the choice |
| Censoring | Delayed reward; no counterfactual after a migration | Same: the policy never learns what moved VMs would have suffered | Same |

## Consequences for the comparison

- **The baseline Narya improved on is a fixed action plan, not a threshold.** The protocol's comparator is P2, a tuned threshold; P5 is a competitor, not the comparator. A reviewer may still ask why a threshold is the right comparator; `reading/levy2020narya.md` records this question.
- **P5 learns online within one run.** Its first weeks are exploration. The 30-day warm-up is not counted, but a 365-day horizon still includes some learning cost, as it would in production.
- **Avoid-allocation is free in GB but not in capacity.** Marked hosts take no arrivals, so marking many hosts raises rejected arrivals, which every run reports. At a zero budget no action of any kind is taken, so P5 equals P0, like every policy.
