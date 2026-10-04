# Benchmark landscape (draft, 4 Oct 2026)

Question: is there an existing open benchmark for failure-mitigation decisions (predicted host failure, then migrate or avoid), and what do comparable benchmarks do that VMMBench should copy?

**Answer: in the sources I checked, no.** The closest items cover other problems. This is a bounded negative result; the search log is at the end and the search is repeated in Week 21 and before submission.

## What comparable benchmarks do

| Item | What it offers | Relevant to VMMBench | Checked |
| --- | --- | --- | --- |
| [Park](https://proceedings.neurips.cc/paper/2019/hash/f69e505b08403ad2298b9f262659929a-Abstract.html) (NeurIPS 2019) | Gym-like environments for 12 systems problems; common `reset`, `step`, observation and action spaces; MIT licence. None of its environments is VM migration or host-failure mitigation | The plug-in API shape; a precedent for systems benchmarks aimed at learning-based policies | GitHub README and NeurIPS page |
| [Gymnasium](https://arxiv.org/abs/2407.17032) | A standard API for reinforcement-learning environments | VMMBench's `Policy` protocol is deliberately not a Gym `step` loop (a policy receives the day's observation and returns a set of actions that fit a budget); borrow the versioning and registration conventions | arXiv page (metadata) |
| [HELM](https://arxiv.org/abs/2211.09110) | A framework for evaluating language models | Fixed scenarios, reporting several metrics side by side, and versioned results are the conventions to copy. I checked only the citation metadata, so what HELM does in detail is from prior knowledge and is to be checked in Week 9 | arXiv page (metadata) |
| [Virt-LM](https://research.spec.org/icpe_proceedings/2011/p307.pdf) (ICPE 2011) | A benchmark for live-migration performance: downtime, total migration time, data migrated, overhead | Closest "benchmark" to migration, but it measures the mechanism on real software, not decision policies | First two pages |
| [DCcluster-Opt](https://arxiv.org/abs/2511.00117) | Open simulation benchmark for scheduling across geo-distributed data centres | Shows data-centre benchmarks with real data exist; its focus is scheduling for carbon, cost and service levels, not failure mitigation | arXiv page (summary) |
| [VM2RL](https://arxiv.org/abs/2505.17359) (EuroSys '25) | Reinforcement learning for VM rescheduling; code and datasets released | An open dataset for rescheduling and fragmentation, not failure mitigation | arXiv page (summary) |
| [CloudSim Plus](https://github.com/cloudsimplus/cloudsimplus), [OpenDC](https://github.com/atlarge-research/opendc) | Simulators with host fault injection (CloudSim Plus) and trace-driven data-centre simulation (OpenDC) | Mechanisms, not benchmarks: no predicted-failure policy, scorer or leaderboard in the pages read | GitHub pages |

## Mitigation systems with no public benchmark

[Narya](https://www.usenix.org/conference/osdi20/presentation/levy), NENYA and Deoxys evaluate on proprietary Microsoft telemetry. From the pages I read, none releases data, a simulator or a scoring harness (Deoxys: none mentioned in the abstract; NENYA: not stated). Narya reports only relative percentages because absolute interruption rates are confidential.

## Data that exists, and its terms

| Data | What it is | Terms stated on the page I read |
| --- | --- | --- |
| [Backblaze Drive Stats](https://www.backblaze.com/cloud-storage/resources/hard-drive-test-data) | Daily SMART and failure records since 2013, quarterly files | Cite Backblaze; you are responsible for your use; derivative works may be sold, the data itself may not |
| [Azure Public Dataset](https://github.com/Azure/AzurePublicDataset) | VM traces 2017 and 2019, packing trace from the Protean paper | Dual licence CC-BY-4.0 and MIT; cite the Resource Central paper for the 2017 traces |
| [Google ClusterData 2019](https://github.com/google/cluster-data) | Eight Borg cells, May 2019 | CC-BY |
| [Alibaba cluster-trace-v2018](https://github.com/alibaba/clusterdata) | About 4,000 machines over 8 days with batch-job DAGs | Licence not on the page I read; confirm before redistribution |
| [LANL failure data](https://www.usenix.org/cfdr-data) | 22 HPC systems, December 1996 to November 2005, node outages with root causes | Acknowledge the data providers |

v1 used a third-party summary of Backblaze data with no licence file; the Week 4 task is to rebuild from Backblaze's own quarterly files under the terms above.

## What this implies for VMMBench

- The gap is real but narrow: there is no open scorer for *decisions* (which VM to move, under a budget) on public failure data. State it as "I found none", never "none exists".
- Design choices to defend: hashed failure worlds shared by every policy (paired comparison), a fixed budget resource, hidden seeds for the leaderboard, versioned results.
- Overlap risk: NENYA and Deoxys are closed, but if either releases data later the "first open benchmark" wording has to change. Recheck in Week 21.

## Search log

| Query or page | Date | Result |
| --- | --- | --- |
| Web search: open benchmark for VM live migration decision policies, host failure prediction, mitigation, leaderboard | 4 Oct 2026 | Virt-LM, OFP-TM and migration-strategy papers; no policy benchmark with a leaderboard |
| Web search: benchmark suite for predictive failure mitigation, RL environment, VM migration, gym | 4 Oct 2026 | Narya, NENYA, VM rescheduling and data-centre control benchmarks; no failure-mitigation benchmark |
| Park GitHub README | 4 Oct 2026 | 12 environments, none on migration or host failures |
| Pages for DCcluster-Opt, VM2RL, Deoxys, NENYA | 4 Oct 2026 | See table; two searches are not exhaustive |
| Not done | | SustainDC (seen only in a search result), a literature database search, the ML-policy benchmark tracks at the venues in `VENUES.md` |
