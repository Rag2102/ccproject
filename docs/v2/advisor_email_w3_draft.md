# Advisor email, Week 3 (draft; not sent)

Send with three attachments or links: `docs/v2/CHARTER.md`, `docs/v2/v1_anomaly.md`, `docs/v2/PROTOCOL.md` (tag `protocol-v0`). Fill in the name. If the Week 1 email has not gone out yet, send that one first or merge the two.

Subject: Protocol draft and a diagnosis of my v1 result: what would you attack first?

Dear Professor <name>,

Following up on my project on workload-aware mitigation of predicted VM failures: I have written down the research plan before collecting any new data, and I would value your critique before I freeze it.

Three short documents are attached:

1. A charter: the thesis, research questions, contributions and non-goals.
2. A diagnosis of my earlier result. The cost-sensitive policy lost to a probability threshold by 3.1% under random placement. I traced most of that to how I counted, not to the policy: the threshold got 8% more migrations, the budget was counted in hosts rather than memory, and a migration was credited with averting failures months later although the decision used a 30-day probability. Under consistent accounting the two policies are within 0.2%.
3. A protocol: the policies, regimes, metrics, the 1% materiality threshold, the 30-comparison confirmatory family with Holm correction, and the decision gates.

What would you attack first? I am especially unsure whether the accounting rule (credit a migration only within the prediction horizon) is the right one, and whether the gate thresholds are sensible.

Thank you,
<name>
