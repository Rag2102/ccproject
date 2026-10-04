# Clark et al., Live Migration of Virtual Machines (NSDI 2005)

Source read: the USENIX PDF, pages 1-12 of 14 (design, writable working sets, implementation, evaluation through the MMuncher example; discussion and references not read).

| Field | Notes |
| --- | --- |
| Problem | Migrate a running OS between hosts with minimal downtime and bounded total migration time (sections 1, 3). |
| Data | Xen on dual Xeon 2 GHz, 2 GB hosts, gigabit switched Ethernet, iSCSI/NAS storage; workloads: web server, SPECweb99, Quake 3 server, a kernel compile, OLTP, SPEC CINT2000 (sections 4, 6). |
| Baseline | Pure stop-and-copy (downtime proportional to memory) and pure demand-migration (long degraded period) (section 3.1). |
| Metric | Downtime and total migration time; data transmitted; effect on service throughput. |
| Claim | Iterative pre-copy gives downtimes as low as 60 ms (Quake 3, 64 MB); 165 ms for a 800 MB web server; 210 ms for SPECweb99 with 350 clients, 960 MB sent for an 800 MB VM (x1.20) (section 6). |
| Limitation | Single LAN, network-attached storage, no local-disk migration; a synthetic writer (MMuncher, section 6.5) is built to dirty memory faster than it can be copied; I did not read its outcome numbers. |
| What we reuse | The pre-copy structure used in `04_workload_criticality_cost.py` and planned for `vmsim/migration.py`: rounds, dirty set, stop condition, downtime from the final round. |
| Reviewer would say | "Your bandwidth and dirty-rate constants are assumed; the original paper measured them." (Fixed by the Week 41-46 testbed.) |

## Details that matter for the v5 simulator

- Rounds: round 1 copies all pages; round n copies the pages dirtied in round n-1 (section 3.1).
- The rate is adaptive. Round 1 runs at an administrator-set minimum rate (100 Mbit/s in the examples); each later round sets the limit to the previous round's dirtying rate plus 50 Mbit/s. Pre-copy stops when the computed rate exceeds the administrator's maximum or fewer than 256 KB remain (section 5.3).
- Downtime has a floor set by the hottest pages in the writable working set, which are always sent in the final stop-and-copy (section 4.2).
- Migrations never used the full link in the experiments; v1's constants (1,250 MB/s link, 150 MB/s maximum dirty rate) are modelling choices, and v1's closed form (memory / (bandwidth minus dirty rate)) is a simplification that I did not find written in these pages. Check this before citing the formula to Clark.
- Non-convergence is a case the paper tests on purpose (section 6.5, a 512 MB host with a program writing constantly to 256 MB), and section 5.5 notes a test program that dirtied memory at 320 Mbit/s, faster than any Ethernet interface. v1 found 100% convergence at Azure's median 10.5% CPU, which is a result about its assumed dirty-rate model, not about real VMs.
