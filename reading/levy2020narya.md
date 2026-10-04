# Levy et al., Narya (OSDI 2020)

Source read: the Microsoft technical report version, "Narya: Predictive and Adaptive Failure Mitigation to Avert Production Cloud VM Interruptions", pages 1-16 (abstract through related work and conclusion; the reference list starts on page 16 and was not read). The OSDI paper is a shorter version, so numbers below are the report's and should be re-checked against the OSDI text before they are quoted.

## Template

| Field | Notes |
| --- | --- |
| Problem | Decide whether a host failure is imminent and which preventive action averts VM interruptions (section 1). |
| Data | Cross-layer telemetry per Azure host: SMART/NVMe health, memory and CPU error logs, device-driver and OS events, control-plane operation errors (section 4.1). Proprietary. |
| Baseline | A "previous static strategy": one fixed plan applied to every predicted-bad node, such as block allocation, try live migration, wait 7 days for short-lived VMs, force migration, then send for repair (section 2.4). It is a fixed action plan, not a probability threshold. |
| Metric | Annual Interruption Rate, AIR = VM interruptions in T / total VM lifetime in T x 365 x 100 VMs (section 3.2). Cost of an action = VM interruptions on the node in the observation window plus interruptions on nodes that received migrated VMs (section 6.1). |
| Claim | 26% average reduction in VM interruptions over the static strategy (nine production experiments, 15 months in production); 26.2% in March 2020, oracle 35.4%, regret 9.2% (section 8.1). |
| Limitation | Cost model is incomplete and needs human review; hardware and firmware failures only; bandit is not contextual yet (section 9). |
| What we reuse | AIR-style cost (interruptions), the idea that action choice is an experiment, the safety-guard vocabulary, the 7-day horizon as a sanity range. |
| Reviewer would say | "Your baseline is a probability threshold; Narya's baseline was a fixed action plan. Why is a threshold the right comparator?" |

## How Narya selects a mitigation (the Sunday-test answer)

1. A predictor flags a node: 51 hand-written rules plus a learned model (gradient-boosted trees on 2,000+ engineered features from 100+ time series; probability cut-off 0.5; prediction horizon 7 days). An attention model gave 5-10% better results than the tree model (section 4).
2. The flag becomes a mitigation request for a (node, prediction rule) pair. The unit of decision is the node and rule, not the VM.
3. A policy tree maps the request to an action distribution. In A/B mode the distribution is fixed by the experiment; in bandit mode it comes from a model served by Resource Central (section 7.2).
4. An action is sampled and passed through safety constraints and rate limits, then applied. Assignment is sticky: the hash of node id and experiment name fixes the group, so a node always sees the same action (section 6.1).
5. The system watches VM interruptions over an observation window (10 to 30 days) and updates the experiment (Welch t-test or ANOVA) or the bandit (Poisson-Gamma Thompson sampling with exponential decay, sigma = 0.99) (sections 6.1-6.3).

## Actions (Table 2)

Primitive: Avoid, Unallocatable (UA), Live Migration (LM), Service Healing, Soft Reboot (SR), Human Investigate (HI). Composite: UA-LM-HI, UA-SR, UA-LM-RH, Avoid-RH. NoOp is the baseline for measuring benefit. The decision engine explores the pre-defined composite actions (section 5); live migration appears inside them after the node is marked unallocatable.

## Corrections to the v5 P5 specification (W15)

v5 describes P5 as actions {nothing, live-migrate, avoid-allocation}, risk buckets, Thompson sampling with Beta posteriors on "interruption avoided", and censored feedback. The paper differs in these ways, all to be listed in `docs/v2/narya_differences.md` in Week 15:

| v5 P5 | Narya (report) |
| --- | --- |
| Beta posterior on a binary "interruption avoided" | Gamma prior on a Poisson rate; the reward is a count of interruptions (cost), choose the lowest sampled cost |
| Three simple actions | Composite actions (UA-LM-HI and others) plus NoOp |
| Context = risk bucket | Context = prediction rule or experiment; one model per experiment; a contextual bandit is listed as future work |
| Feedback "censored after a migration" | Delayed reward over 10-30 days; exponential decay; sticky actions; minimum and maximum action probabilities (10% exploration below 100 flagged nodes per day, 5% above); a "premature" flag falls back to A/B probabilities |
| (none) | Counterfactual estimation (inverse propensity scoring) is used to evaluate, not to act; I did not find the phrase "censored feedback" in the text |

## Where Narya is silent (matters for the charter)

- No per-VM criticality and no explicit VM-size or migration-cost term in the decision. VM size is named as a factor affecting outcomes (section 1), and not every VM can be live migrated (section 5), but the decision is per node and rule.
- Absolute AIR values and cost units are confidential (results are relative percentages, costs in "anonymized units"), the rules and thresholds are not published, and the telemetry is not available. This is why a public-data benchmark is not a re-implementation.
- v1's claim that a probability threshold is "functionally similar to the static strategy Narya improves on" is not supported by this text. Narya's ML predictor does use a 0.5 cut-off, but the 26% comes from choosing among actions, not from replacing a threshold.
