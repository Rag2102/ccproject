# Wang et al., NENYA: Cascade Reinforcement Learning for Cost-Aware Failure Mitigation at Microsoft 365 (KDD 2022)

Source read: the ACM version, DOI 10.1145/3534678.3539127, pages 4032-4040, in full (1 Nov 2026).

| Field | Notes |
| --- | --- |
| Problem | Proactive mitigation for Microsoft 365 database copies: decide whether to act and which action, per database copy, hourly (sections 3, 5). |
| Data | Microsoft 365 production logs. Size, absolute period and data are not published. Offline evaluation replays logs, assuming mitigation does not change a copy's static features (section 4.1). |
| Baseline | Random, rule-based reactive, Narya, SAC, DDPG (Table 1). No probability threshold tuned to a budget. |
| Metric | AvgAdbFailureRate and AvgCost (section 4.1.2). |
| Claim | Offline: AvgCost 3.529 and failure rate 0.65%, against 9.753 and 1.46% for Narya (Table 1). Online since Nov 2021: failure rate improved 5.46%, cost 25.87% (section 5). |
| Method | RL (built on DDPG) with two NoOp layers filtering out most copies, then one Op layer choosing SwitchIn, SwitchOut or Replace. Fewer than 1 in 1,000 copies reach the Op layer (section 3.3). |
| Cost model | Fixed per action type, set with domain experts: Switch −1, Replace −100, NoOp 0. Added to the negative predicted failure probability (section 3.1). |
| Limitation | One operator; no code or data; no theory of when it pays; rewards rely on a learned failure model; offline transition is a log replay. |

## Against this project

- **It does not have:** per-instance criticality or cost (cost depends on the action type, not on what the instance runs), a resource budget, placement avoidance as an action, a theory of when cost awareness pays, public data or an artifact.
- **It is proactive** and it is cost-aware. So "we are the cost-aware one" is not a novelty claim over NENYA. Its authors claim the first end-to-end method that considers mitigation cost for whether and which action.
- **It supports two findings here.** Its gain comes largely from choosing no action: Table 2 shows cascade layers cutting cost and failures, which fits BAM's gain coming from declining bad moves. Its case study (section 4.4) shows Narya's 0.5 cut-off missing rising risk and firing on temporary spikes, which fits the harm a threshold can do; ours is shown under a budget.
- **Reviewer would say:** "NENYA already learns cost-aware decisions; why not RL here?" Answer: the question differs. It learns a policy for one operator; this work asks when workload-aware ranking helps, on public data. No RL policy is in this benchmark yet, and adding one is possible through the policy API.
- **Careful with the comparison:** Table 1 compares methods on its own replay; Deoxys's Table 1 compares Narya and NENYA in a private simulator. Neither can be compared with this project's numbers.
