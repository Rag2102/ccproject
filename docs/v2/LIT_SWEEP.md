# Literature sweep for the novelty claims (1 Nov 2026)

A short web search, not a systematic review: four searches, reading titles and result summaries. It backs "to our knowledge" and does not justify "first". Papers below were **not read in full** unless noted. Repeat within the last 12 months before submission (Week 34), and through the ACM and IEEE libraries.

## NENYA full text

Not reachable by search; the owner supplied the PDF and it is read: `reading/wang2022nenya.md`.

## N1: criticality against machine risk in public traces

Nothing found that measures this directly. Closest:
- [Bappy et al., A Deep Dive into the Google Cluster Workload Traces](https://arxiv.org/pdf/2308.02358): 2019 trace; job outcomes by priority and scheduling class. This is about job failure, not machine risk. **Read before the claim is made, and cite it.**
- [Sîrbu and Babaoglu, Towards Operator-less Data Centers](https://arxiv.org/pdf/1606.04456): node failure prediction on an earlier Google trace.
- Task-failure prediction such as [this study](https://www.iieta.org/journals/mmep/paper/10.18280/mmep.090234) uses priority as a feature; it does not relate placement to machine risk.

Status: holds as "to our knowledge". Author names above come from memory or result pages and need checking before citation.

## N3: open benchmark for failure-mitigation decisions

Nothing found with public failure worlds, a shared migration budget and frozen paired comparison. Nearby benchmarks have another target:
- [CloudIR-Bench](https://arxiv.org/html/2610.29185): incident reports, root cause and mitigation prediction with LLMs.
- [Cloud-OpsBench](https://arxiv.org/html/2603.00468): root cause analysis agents on Kubernetes.
- [SREGym](https://arxiv.org/pdf/2605.07161): a live benchmark for AI SRE agents.
- [SuperBench](https://arxiv.org/html/2402.06194v2): proactive validation of cloud AI infrastructure, with policy evaluation. Closest in spirit; read it.

Status: holds as "to our knowledge". These are worth citing to show the difference: they evaluate diagnosis by agents, and this one evaluates pre-failure placement and migration decisions under a budget.

## N4: avoidance against migration

Nothing found that isolates it on public data, but the search was thin. Narya and Protean already contain avoidance, so the idea is not new. Search again with "predictive placement" and "hardware failure", and check SoCC, EuroSys and OSDI directly.

## Proactive migration work seen

[Proactive live migration for VNFs (CNSM 2021)](https://dl.ifip.org/db/conf/cnsm/cnsm2021/1570733268.pdf) and [proactive VM replication in OpenNebula (Computing 2025)](https://dl.acm.org/doi/10.1007/s00607-025-01476-1): neither shows a criticality-aware budget in what was seen.

## N7 and N8 (2 Nov 2026, three searches, so thin)

- **Destination risk in the migration decision.** [US 9277002](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9277002) and [US 9584389](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9584389), "Physical resource management": expected cost of migrating as cost times the probability of failure if the VM is migrated. Only excerpts seen; it may mean failure of the migration rather than of the destination host. Read before the paper. No research paper found that charges it, but this is absence from a thin search.
- **Per-tier closure.** Nothing found. Nearby: [a node-error patent application](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12216552) allocates new VMs to healthier nodes (all VMs, no tiers); [Lin et al. node failure prediction](https://www.researchgate.net/publication/328592012_Predicting_Node_failure_in_cloud_service_systems) is the research form. Protean has priority and "likely to fail" preference rules, whose mechanism was not read, so that is the first thing to check. Spot and evictable VMs on risky nodes would be the closest idea, and these searches did not settle whether it exists.

Status: state both over the three base papers only.
