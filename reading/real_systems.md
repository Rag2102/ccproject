# Real-system analogues: OpenStack Watcher and KubeVirt

Sources: Watcher documentation pages for strategies, the Host Maintenance strategy and actions; KubeVirt live-migration user guide (all fetched 4 Oct 2026; documentation of current releases, so values may change).

## OpenStack Watcher

| Item | What the documentation says |
| --- | --- |
| Strategies | 13 listed; three migrate VMs (VM Workload Consolidation, Workload Balance Migration, Zone Migration). Hardware-oriented ones: Host Maintenance, Outlet Temperature, Uniform Airflow. None is a failure-prediction strategy. |
| Actions | Migrate (live or cold), Change Nova Service State, Change Node Power State, Resize, Shelve, Stop, Delete, Volume Migration; Nop and Sleep are for testing. |
| Host Maintenance | Migrates all instances off one node, then disables the node's nova-compute service. Inputs: maintenance node, optional backup node, flags to disable live or cold migration. Live migration for active instances by default. |
| Cost fields | Not found in the pages read. Actions have scheduling weights (migrate 30, change service state 50) that order the plan; they are not costs. |

## KubeVirt

| Item | What the documentation says |
| --- | --- |
| Bandwidth | 64 MiB/s per migration by default (`bandwidthPerMigration`). |
| Concurrency | 5 migrations per cluster and 2 outbound per node by default. |
| Timeouts | Completion timeout 800 s per GiB of VM memory and disk; progress timeout 150 s. |
| Strategies | Pre-copy by default; optional post-copy and auto-converge (CPU throttling; off by default). |
| Non-convergence | With workload disruption disallowed the migration is cancelled and may restart; if allowed, it switches to post-copy or pauses the VM. |
| Cost fields | None documented as costs; the tunables above are the limits an operator can set. |

## "Real-system analogue" column for T5

- The v5 migration model (rounds, concurrency queue, non-convergence) matches KubeVirt's per-migration bandwidth, concurrency limit and timeout. Use the 64 MiB/s default and the 800 s/GiB timeout as realistic points when sweeping the bandwidth and cost-error grid.
- Watcher's Host Maintenance is the real analogue of "evacuate a host": the action set is migrate plus disable-allocation, similar to Narya's Unallocatable plus Live Migration. Neither system chooses which VMs to move by predicted failure probability, VM criticality and a budget, which is the decision VMMBench evaluates.
