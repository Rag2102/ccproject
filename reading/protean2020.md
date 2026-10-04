# Hadary et al., Protean: VM Allocation Service at Scale (OSDI 2020)

Source read: the USENIX PDF, pages 1-7 of 16 (introduction, background, workload analysis, rule-based allocation agent). Later sections (caching, evaluation, COVID case study) not read.

| Field | Notes |
| --- | --- |
| Problem | Place millions of VMs per day on 10-100k-machine zones with low latency, high utilisation and few rejections. |
| Data | Azure production plus simulation; a supplementary trace is released. |
| Baseline | Not reviewed in the pages read. |
| Metric | Allocation latency (about 20 ms per VM), throughput, rejection rate, utilisation (85-90% on a key metric). |
| Claim | A rule-based Allocation Agent separates policy from mechanism: validator rules filter hard constraints, preference rules score soft ones, in a two-level (cluster, then machine) hierarchy with about 100 rules (section 3). |
| Limitation | Not reviewed. |
| What we reuse | Facts about how placement is decided, for the transplant caveat in the rho definition. |
| Reviewer would say | "Placement in Azure is not random, so what does your random or copula placement stand for?" |

## Relevance to rho

- Placement is driven by packing quality, fault-domain spread, hardware type, balance across clusters and priority; examples include best-fit, prefer non-empty machines and prefer emptier clusters (section 3.2).
- Protean avoids machines that are "not ready", not updated or "likely to fail in the near future" (section 3.1). If so, health-aware allocation could push new critical VMs away from risky hosts, which would make the criticality-risk correlation negative for new allocations. I read only the statement of the requirement, not how it is implemented.
- Low-priority VMs (Batch, Spot) can be evicted, which links priority to preemption rather than to hardware risk.
- Together with Resource Central, this supports treating rho as an empirical unknown (W8) and keeping the "transplant" caveat: v5 measures rho in Google 2019 traces and transplants it to Backblaze-driven hosts.
