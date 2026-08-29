"""
Task 5 -- Workload criticality + migration cost modeling.

Task 2 already derived criticality (from Azure's real `vm_category`) and a
first-pass migration-cost proxy (memory + vCPU count). This task replaces
that placeholder proxy with an actual migration-cost *model*, grounded in
the standard pre-copy live-migration formula from the systems literature
(Clark et al., "Live Migration of Virtual Machines", NSDI 2005), and puts
migration cost and failure cost on a comparable "customer-impact-minutes"
scale so task 6's decision rule can weigh them against each other honestly.

IMPORTANT — what's real data vs. modeling assumption in this file:
  - memory_gb, vcores, avg_cpu: real, per-VM, from the Azure trace.
  - the *parameters* translating those into a migration duration/cost
    (network bandwidth, dirty-page rate at 100% CPU, stop-and-copy fallback
    time, unmitigated-failure recovery time) are modeling assumptions from
    published ranges, not measured Azure infrastructure numbers -- no public
    dataset exposes Azure's actual live-migration network telemetry. Each
    one is named as a constant below with its source/rationale so it can be
    swapped or sensitivity-tested rather than being buried in the math.

Run from the project root: python3 scripts/04_workload_criticality_cost.py
"""
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

# ---------------------------------------------------------------------------
# Documented assumptions (all in one place, all named, all overridable)
# ---------------------------------------------------------------------------
MIGRATION_BANDWIDTH_MBPS = 1250        # ~10 Gbps inter-host migration network (typical modern DC fabric)
MAX_DIRTY_RATE_MBPS_AT_100PCT_CPU = 150  # memory-write rate a fully-busy VM can sustain (Clark et al. 2005 report
                                          # tens-to-a-few-hundred MB/s for write-heavy workloads; mid-range value used)
STOPCOPY_FALLBACK_S = 60               # forced final stop-and-copy pause if pre-copy never converges (worst case,
                                        # consistent with Hyper-V/VMware docs describing a bounded max pre-copy budget)
UNMITIGATED_FAILURE_DOWNTIME_MIN = 10  # assumed customer-visible downtime if a host fails with *no* mitigation
                                        # (detect + reallocate + reboot elsewhere) -- no public ground truth for this;
                                        # treated as a sensitivity parameter, not a measured constant (see task5_summary.md)

vm = pd.read_csv(PROCESSED / "azure_vms_clean.csv.gz")
print(f"Loaded {len(vm):,} VMs")

# ---------------------------------------------------------------------------
# 1. Migration cost model (pre-copy convergence formula)
#    T_precopy = memory / (bandwidth - dirty_rate), only converges if
#    dirty_rate < bandwidth. avg_cpu is used (not max_cpu) as the dirty-page
#    driver because pre-copy duration depends on *sustained* memory-write
#    activity over the whole transfer, not brief bursts.
# ---------------------------------------------------------------------------
memory_mb = vm["memory_gb"] * 1024
dirty_rate_mbps = (vm["avg_cpu"] / 100.0) * MAX_DIRTY_RATE_MBPS_AT_100PCT_CPU

vm["precopy_converges"] = dirty_rate_mbps < (0.9 * MIGRATION_BANDWIDTH_MBPS)  # 10% safety margin, not exactly at the limit
headroom = np.where(vm["precopy_converges"], MIGRATION_BANDWIDTH_MBPS - dirty_rate_mbps, np.nan)
vm["migration_time_est_s"] = memory_mb / headroom

# Two distinct cost components, deliberately kept separate:
#  (a) infra/resource cost: total pre-copy duration -- ties up source+dest
#      host bandwidth and CPU, but is NOT customer-visible (VM keeps running).
#  (b) customer-facing cost: the brief final stop-and-copy blackout, which
#      IS visible, and which blows up to STOPCOPY_FALLBACK_S if pre-copy
#      never converged and the hypervisor has to force a hard cutover.
BASE_BLACKOUT_S = 1.0  # typical converged live-migration blackout window is sub-second to ~1s
vm["migration_blackout_s"] = np.where(vm["precopy_converges"], BASE_BLACKOUT_S, STOPCOPY_FALLBACK_S)
vm.loc[~vm["precopy_converges"], "migration_time_est_s"] = STOPCOPY_FALLBACK_S  # non-convergent case: bounded, not infinite

# Customer-impact cost of *migrating*, in the same "impact-minutes" unit
# that failure cost will use, weighted by workload criticality (a blackout on
# an Interactive VM is felt; the same blackout on a Delay-insensitive batch
# job mostly isn't).
vm["migration_customer_cost_min"] = (vm["migration_blackout_s"] / 60.0) * vm["criticality_weight"]
# Infra resource cost, kept as its own column (minutes of host bandwidth tied up) --
# this is what makes an *unnecessary* migration wasteful even when the customer
# never notices the blackout: it still burns real infrastructure capacity.
vm["migration_resource_cost_min"] = vm["migration_time_est_s"] / 60.0

print(f"\nPre-copy convergence: {vm['precopy_converges'].mean():.2%} of VMs converge normally "
      f"(median avg_cpu={vm['avg_cpu'].median():.1f}%, so most VMs are far from saturating "
      f"the {MIGRATION_BANDWIDTH_MBPS} MB/s migration link)")
print(f"Non-convergent VMs (forced stop-and-copy fallback): {(~vm['precopy_converges']).sum():,}")
print("\nMigration resource cost (minutes) by size tier:\n",
      vm.groupby("size_tier")["migration_resource_cost_min"].describe()[["mean", "50%", "max"]])

# ---------------------------------------------------------------------------
# 2. Failure cost model -- the other side of the ledger for task 6
#    Cost of an *unmitigated* failure = assumed hard-recovery downtime,
#    scaled by how much that workload's customers actually feel downtime.
# ---------------------------------------------------------------------------
vm["failure_customer_cost_min"] = UNMITIGATED_FAILURE_DOWNTIME_MIN * vm["criticality_weight"]

print("\nFailure cost (customer-impact-minutes, if unmitigated) by criticality tier:\n",
      vm.groupby("criticality_tier")["failure_customer_cost_min"].agg(["mean", "count"]))

# ---------------------------------------------------------------------------
# 3. Sanity checks
# ---------------------------------------------------------------------------
# Every unnecessary migration should cost far less than an unmitigated
# customer-impacting failure for the same VM, on the customer-facing axis --
# otherwise "always migrate" would trivially beat any threshold policy and
# the comparison in task 8 would be meaningless.
ratio = vm["failure_customer_cost_min"] / vm["migration_customer_cost_min"].replace(0, np.nan)
print(f"\nSanity check -- failure cost / migration customer-cost ratio: "
      f"min={ratio.min():.1f}x, median={ratio.median():.1f}x, "
      f"(should be >>1 for nearly all VMs -- a wrongly-triggered migration "
      f"should be far cheaper than a failure that actually happens)")
assert (ratio > 1).mean() > 0.99, "Migration cost is not consistently cheaper than failure cost -- check assumptions"

out_cols = list(vm.columns)
vm.to_csv(PROCESSED / "azure_vms_with_costs.csv.gz", index=False, compression="gzip")
print(f"\nSaved -> data/processed/azure_vms_with_costs.csv.gz ({len(vm):,} rows, {len(out_cols)} columns)")
print("\nDone.")
