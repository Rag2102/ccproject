"""
Task 8 -- Replay/evaluation simulator. Not a general cloud simulator
(CloudSim/SimGrid) -- see docs/project_scope.md section 6 for why that
would be the wrong tool. This is a purpose-built replay: for every real
Backblaze drive (= a host), walk forward through its *actual* real health
trajectory in 30-day steps, let each policy decide migrate/wait at every
step using only information available at that step, and score what
actually happened.

Key modeling decisions, stated explicitly:
  - A host's real fate (whether/when it failed) is a fixed fact from the
    dataset -- migrating its VMs away does not change whether the physical
    hardware fails, only whether that failure becomes customer-impacting.
    So both policies can be evaluated against the SAME realized host
    trajectory without needing two diverging simulations.
  - Real VMs (Azure trace) are assigned to real hosts (Backblaze drives)
    uniformly at random, ONCE, and that identical assignment is used for
    both policies -- there is no public dataset linking real VM placement
    to real host failures (see docs/project_scope.md section 5), so this
    is the unbiased default; fairness of the comparison only requires that
    both policies see the same workload-to-host mapping, which they do.
  - A migration decision made at the start of the 30-day interval
    containing the real failure day still counts as "caught in time" --
    live migration (task 5) takes seconds to low-single-digit minutes,
    negligible against a 30-day decision granularity.

Run from the project root: python3 scripts/06_simulation_evaluation.py
"""
import numpy as np
import pandas as pd
from pathlib import Path
from policy import cost_sensitive_decision, threshold_decision

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
RNG_SEED = 42

# ---------------------------------------------------------------------------
# 1. Load hosts (real Backblaze drives) and the hazard/TTF lookup (real
#    per-30-day-bin model)
# ---------------------------------------------------------------------------
drv = pd.read_csv(PROCESSED / "backblaze_drives_clean.csv").dropna(subset=["age_days"]).reset_index(drop=True)
ttf_lookup = pd.read_csv(PROCESSED / "ttf_lookup_table.csv")
top_models = sorted(ttf_lookup.loc[ttf_lookup["model_grp"] != "OTHER", "model_grp"].unique())

drv["host_id"] = np.arange(len(drv))
drv["model_grp"] = np.where(drv["model"].isin(top_models), drv["model"], "OTHER")
print(f"Hosts (real drives): {len(drv):,}  |  real failures: {drv['failed'].sum():,} "
      f"({drv['failed'].mean():.2%})")

# ---------------------------------------------------------------------------
# 2. Assign real VMs to real hosts, uniformly at random, once -- identical
#    for both policies.
# ---------------------------------------------------------------------------
vm = pd.read_csv(PROCESSED / "azure_vms_with_costs.csv.gz")
rng = np.random.default_rng(RNG_SEED)
vm = vm.copy()
vm["host_id"] = rng.integers(0, len(drv), size=len(vm))
vm["total_migration_cost_min"] = vm["migration_resource_cost_min"] + vm["migration_customer_cost_min"]

host_costs = vm.groupby("host_id").agg(
    n_vms=("vm_id", "size"),
    failure_cost_host=("failure_customer_cost_min", "sum"),
    migration_cost_host=("total_migration_cost_min", "sum"),
    max_criticality=("criticality_tier", lambda s: s.value_counts().idxmax()),
).reset_index()
hosts = drv.merge(host_costs, on="host_id", how="left")
n_empty = hosts["n_vms"].isna().sum()
hosts["n_vms"] = hosts["n_vms"].fillna(0)
hosts["failure_cost_host"] = hosts["failure_cost_host"].fillna(0.0)
hosts["migration_cost_host"] = hosts["migration_cost_host"].fillna(0.0)
print(f"VMs assigned to hosts: {len(vm):,} across {len(drv):,} hosts "
      f"(mean {len(vm)/len(drv):.1f} VMs/host, {n_empty} hosts got none)")

# ---------------------------------------------------------------------------
# 3. Baseline threshold, carried over from task 6/7's calibration
# ---------------------------------------------------------------------------
TAU = ttf_lookup["p_fail_within_window"].quantile(0.95)
print(f"Baseline threshold tau = {TAU:.5f} (95th percentile of real host risk states)")

# ---------------------------------------------------------------------------
# 4. Per model group, vectorized: for every host in the group, find the
#    first bin at which each policy would migrate (if any), respecting that
#    decisions are only valid before the host's own cutoff (its real
#    failure day, or the day observation of it ended).
# ---------------------------------------------------------------------------
def first_migrate_bin(migrate_bool_matrix, bin_starts):
    """migrate_bool_matrix: (H, B). Returns bin_start_days of first True per
    row, or NaN if none."""
    any_migrate = migrate_bool_matrix.any(axis=1)
    first_idx = migrate_bool_matrix.argmax(axis=1)  # first True index (valid only where any_migrate)
    t_migrate = np.where(any_migrate, bin_starts[first_idx], np.nan)
    return t_migrate

results = []
for grp, g in hosts.groupby("model_grp"):
    bins = ttf_lookup[ttf_lookup["model_grp"] == grp].sort_values("bin_start_days")
    bin_starts = bins["bin_start_days"].values.astype(float)         # (B,)
    p_fail_row = bins["p_fail_within_window"].values.reshape(1, -1)   # (1,B)
    ttf_row = bins["expected_ttf_days"].values.reshape(1, -1)         # (1,B)

    failure_cost_col = g["failure_cost_host"].values.reshape(-1, 1)   # (H,1)
    migration_cost_col = g["migration_cost_host"].values.reshape(-1, 1)
    cutoff_col = g["age_days"].values.reshape(-1, 1)                  # (H,1)

    valid = bin_starts.reshape(1, -1) < cutoff_col                    # (H,B)

    cs = cost_sensitive_decision(p_fail_row, ttf_row, failure_cost_col, migration_cost_col)
    cs_migrate = cs["migrate"] & valid

    thresh_migrate = threshold_decision(p_fail_row, TAU) & valid

    g = g.copy()
    g["t_migrate_cost_sensitive"] = first_migrate_bin(cs_migrate, bin_starts)
    g["t_migrate_threshold"] = first_migrate_bin(thresh_migrate, bin_starts)
    results.append(g)

hosts_out = pd.concat(results, ignore_index=True)

# ---------------------------------------------------------------------------
# 5. Classify outcomes and cost per policy
# ---------------------------------------------------------------------------
def classify(df, t_migrate_col):
    migrated = df[t_migrate_col].notna()
    outcome = np.select(
        [df["failed"].eq(1) & migrated, df["failed"].eq(1) & ~migrated,
         df["failed"].eq(0) & migrated, df["failed"].eq(0) & ~migrated],
        ["necessary_migration", "customer_impacting_failure",
         "unnecessary_migration", "correct_inaction"],
        default="unknown",
    )
    cost = np.select(
        [outcome == "necessary_migration", outcome == "customer_impacting_failure",
         outcome == "unnecessary_migration", outcome == "correct_inaction"],
        [df["migration_cost_host"], df["failure_cost_host"], df["migration_cost_host"], 0.0],
    )
    return outcome, cost

for policy_name, col in [("cost_sensitive", "t_migrate_cost_sensitive"), ("threshold", "t_migrate_threshold")]:
    outcome, cost = classify(hosts_out, col)
    hosts_out[f"outcome_{policy_name}"] = outcome
    hosts_out[f"cost_{policy_name}"] = cost

hosts_out.to_csv(PROCESSED / "simulation_results_per_host.csv", index=False)
print(f"\nSaved -> data/processed/simulation_results_per_host.csv ({len(hosts_out):,} rows)")

# ---------------------------------------------------------------------------
# 6. Headline comparison
# ---------------------------------------------------------------------------
print("\n" + "=" * 78)
print("HEADLINE RESULTS")
print("=" * 78)
summary = {}
for policy_name in ["cost_sensitive", "threshold"]:
    counts = hosts_out[f"outcome_{policy_name}"].value_counts()
    total_cost = hosts_out[f"cost_{policy_name}"].sum()
    n_failed = hosts_out["failed"].sum()
    n_censored = (hosts_out["failed"] == 0).sum()
    summary[policy_name] = {
        "necessary_migrations": counts.get("necessary_migration", 0),
        "customer_impacting_failures": counts.get("customer_impacting_failure", 0),
        "unnecessary_migrations": counts.get("unnecessary_migration", 0),
        "correct_inactions": counts.get("correct_inaction", 0),
        "total_migrations": counts.get("necessary_migration", 0) + counts.get("unnecessary_migration", 0),
        "customer_impacting_failure_rate": counts.get("customer_impacting_failure", 0) / n_failed,
        "unnecessary_migration_rate": counts.get("unnecessary_migration", 0) / n_censored,
        "total_cost_impact_min": total_cost,
    }

summary_df = pd.DataFrame(summary).T
pd.set_option("display.width", 120)
print(summary_df.to_string())

cs, th = summary["cost_sensitive"], summary["threshold"]
print("\n--- Cost-sensitive vs. threshold baseline ---")
print(f"Customer-impacting failures : {cs['customer_impacting_failures']:.0f} vs {th['customer_impacting_failures']:.0f}  "
      f"({(1 - cs['customer_impacting_failures']/th['customer_impacting_failures']):+.1%} relative change)"
      if th['customer_impacting_failures'] else "")
print(f"Unnecessary migrations      : {cs['unnecessary_migrations']:.0f} vs {th['unnecessary_migrations']:.0f}  "
      f"({(1 - cs['unnecessary_migrations']/th['unnecessary_migrations']):+.1%} relative change)"
      if th['unnecessary_migrations'] else "")
print(f"Total migrations triggered  : {cs['total_migrations']:.0f} vs {th['total_migrations']:.0f}")
print(f"Total cost impact (min)     : {cs['total_cost_impact_min']:.1f} vs {th['total_cost_impact_min']:.1f}  "
      f"({(1 - cs['total_cost_impact_min']/th['total_cost_impact_min']):+.1%} relative change)")

summary_df.to_csv(PROCESSED / "simulation_headline_summary.csv")
print(f"\nSaved -> data/processed/simulation_headline_summary.csv")

# ---------------------------------------------------------------------------
# 7. The comparison above is honest but not yet a fair one: tau=0.00731 (95th
#    percentile of risk) and the cost-sensitive rule land at very different
#    overall aggressiveness levels (7,980 vs 5,116 total migrations) purely
#    because of how the task-5 cost constants happen to be calibrated --
#    that's an arbitrary artifact of two independently-chosen operating
#    points, not evidence about which *targeting logic* is better. The
#    principled comparison is: give both policies the SAME migration budget
#    (same total number of migrations) and see which one spends it on the
#    hosts that actually mattered. This is standard practice when comparing
#    classifiers/policies that can each be tuned to any operating point --
#    e.g. comparing at matched recall or matched flagged-rate instead of at
#    two independently-chosen thresholds.
# ---------------------------------------------------------------------------
print("\n" + "=" * 78)
print("FAIR COMPARISON AT MATCHED MIGRATION BUDGET")
print("=" * 78)

def threshold_first_migrate_all(tau):
    out = pd.Series(index=hosts_out.index, dtype=float)
    for grp, g in hosts_out.groupby("model_grp"):
        bins = ttf_lookup[ttf_lookup["model_grp"] == grp].sort_values("bin_start_days")
        bin_starts = bins["bin_start_days"].values.astype(float)
        p_fail_row = bins["p_fail_within_window"].values.reshape(1, -1)
        cutoff_col = g["age_days"].values.reshape(-1, 1)
        valid = bin_starts.reshape(1, -1) < cutoff_col
        migrate = threshold_decision(p_fail_row, tau) & valid
        out.loc[g.index] = first_migrate_bin(migrate, bin_starts)
    return out

target_migrations = int(cs["total_migrations"])
lo, hi = TAU, ttf_lookup["p_fail_within_window"].max()
for _ in range(25):
    mid = (lo + hi) / 2
    n = threshold_first_migrate_all(mid).notna().sum()
    if n > target_migrations:
        lo = mid
    else:
        hi = mid
# The achievable migration counts jump in large discrete steps (many hosts
# share the same model_grp/age hazard value, so many first-crossings shift
# at once) -- an exact match to the target usually isn't achievable. Take
# whichever of the two bisection bounds lands closer to the target rather
# than silently accepting an under-shoot.
t_migrate_lo = threshold_first_migrate_all(lo)
t_migrate_hi = threshold_first_migrate_all(hi)
n_lo, n_hi = t_migrate_lo.notna().sum(), t_migrate_hi.notna().sum()
if abs(n_lo - target_migrations) <= abs(n_hi - target_migrations):
    tau_matched, t_migrate_matched = lo, t_migrate_lo
else:
    tau_matched, t_migrate_matched = hi, t_migrate_hi
hosts_out["t_migrate_threshold_matched"] = t_migrate_matched
outcome_m, cost_m = classify(hosts_out, "t_migrate_threshold_matched")
hosts_out["outcome_threshold_matched"] = outcome_m
hosts_out["cost_threshold_matched"] = cost_m

counts_m = pd.Series(outcome_m).value_counts()
n_matched_migrations = counts_m.get("necessary_migration", 0) + counts_m.get("unnecessary_migration", 0)
print(f"Matched threshold tau = {tau_matched:.5f}  ->  {n_matched_migrations:.0f} total migrations "
      f"(target was cost-sensitive's {target_migrations:,})")
print(f"\n{'metric':38s}{'cost-sensitive':>18s}{'threshold (matched budget)':>28s}")
print(f"{'customer-impacting failures':38s}{cs['customer_impacting_failures']:>18.0f}"
      f"{counts_m.get('customer_impacting_failure', 0):>28.0f}")
print(f"{'necessary migrations':38s}{cs['necessary_migrations']:>18.0f}"
      f"{counts_m.get('necessary_migration', 0):>28.0f}")
print(f"{'unnecessary migrations':38s}{cs['unnecessary_migrations']:>18.0f}"
      f"{counts_m.get('unnecessary_migration', 0):>28.0f}")
print(f"{'total cost impact (customer-min)':38s}{cs['total_cost_impact_min']:>18.1f}"
      f"{cost_m.sum():>28.1f}")

cost_delta_pct = (cost_m.sum() - cs["total_cost_impact_min"]) / cost_m.sum()
print(f"\nAt an EQUAL migration budget, cost-sensitive's total cost is "
      f"{'lower' if cs['total_cost_impact_min'] < cost_m.sum() else 'higher'} than the threshold's "
      f"by {abs(cost_delta_pct):.1%} -- this, not the mismatched-budget numbers above, is the "
      f"real test of whether cost-aware targeting beats probability-only targeting.")

hosts_out.to_csv(PROCESSED / "simulation_results_per_host.csv", index=False)
print(f"\nSaved -> data/processed/simulation_results_per_host.csv (updated with matched-budget columns)")
print("\nDone.")
