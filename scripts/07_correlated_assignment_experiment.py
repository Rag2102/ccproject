"""
Task 9 (experiment 1) -- Does cost-aware targeting help once workload cost
actually correlates with real hardware failure risk?

Task 8's random VM-to-host assignment makes cost/criticality statistically
independent of a host's real hazard by construction -- there's no
exploitable relationship for cost-awareness to find, which is the most
likely reason the plain probability threshold matched or slightly beat the
cost-sensitive policy there. This script tests the natural follow-up: sweep
a controlled correlation strength rho between VM criticality and host risk,
re-run the exact same replay simulation at each rho, and see whether (and
at what rho) the cost-sensitive policy's advantage actually appears.

Correlation is induced with a standard rank-blending method (a simplified
Iman-Conover approach): each VM gets a random percentile and a
criticality-rank percentile; blending them by rho, then sorting VMs and
"host slots" (each host repeated by its VM capacity) by their respective
scores and pairing them index-for-index, produces an assignment with
approximately the target Spearman rank correlation, while (at rho=0)
reducing back to task 8's uniform-random case for continuity.

Run from the project root: python3 scripts/07_correlated_assignment_experiment.py
"""
import numpy as np
import pandas as pd
from pathlib import Path
from policy import cost_sensitive_decision, threshold_decision

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
RNG_SEED = 42
RHO_VALUES = [0.0, 0.3, 0.6, 0.9]

drv = pd.read_csv(PROCESSED / "backblaze_drives_clean.csv").dropna(subset=["age_days"]).reset_index(drop=True)
ttf_lookup = pd.read_csv(PROCESSED / "ttf_lookup_table.csv")
top_models = sorted(ttf_lookup.loc[ttf_lookup["model_grp"] != "OTHER", "model_grp"].unique())
drv["host_id"] = np.arange(len(drv))
drv["model_grp"] = np.where(drv["model"].isin(top_models), drv["model"], "OTHER")

vm = pd.read_csv(PROCESSED / "azure_vms_with_costs.csv.gz").copy()
vm["total_migration_cost_min"] = vm["migration_resource_cost_min"] + vm["migration_customer_cost_min"]

# Host risk score used ONLY to induce the correlation (a static per-model-
# group summary of real hazard), not used inside the actual decision logic,
# which still runs on the full dynamic p_fail_within_window/TTF as before.
host_risk = ttf_lookup.groupby("model_grp")["p_fail_within_window"].mean().rename("host_risk_score")
drv = drv.merge(host_risk, on="model_grp", how="left")

TAU = ttf_lookup["p_fail_within_window"].quantile(0.95)


def assign_vms_correlated(rho, seed=RNG_SEED):
    rng = np.random.default_rng(seed)
    n_vms, n_hosts = len(vm), len(drv)
    capacity = np.full(n_hosts, n_vms // n_hosts)
    capacity[: n_vms % n_hosts] += 1  # distribute remainder
    host_slots = np.repeat(drv["host_id"].values, capacity)
    host_slot_risk = np.repeat(drv["host_risk_score"].values, capacity)

    crit_rank_pct = vm["criticality_weight"].rank(method="first", pct=True).values
    u = rng.uniform(size=n_vms)
    blended_vm_score = rho * crit_rank_pct + (1 - rho) * u

    vm_order = np.argsort(blended_vm_score)
    slot_order = np.argsort(host_slot_risk)
    assigned_host = np.empty(n_vms, dtype=host_slots.dtype)
    assigned_host[vm_order] = host_slots[slot_order]

    v = vm.copy()
    v["host_id"] = assigned_host
    return v


def build_hosts(v):
    host_costs = v.groupby("host_id").agg(
        n_vms=("vm_id", "size"),
        failure_cost_host=("failure_customer_cost_min", "sum"),
        migration_cost_host=("total_migration_cost_min", "sum"),
    ).reset_index()
    h = drv.merge(host_costs, on="host_id", how="left")
    h[["n_vms", "failure_cost_host", "migration_cost_host"]] = h[
        ["n_vms", "failure_cost_host", "migration_cost_host"]
    ].fillna(0.0)
    return h


def first_migrate_bin(migrate_bool_matrix, bin_starts):
    any_migrate = migrate_bool_matrix.any(axis=1)
    first_idx = migrate_bool_matrix.argmax(axis=1)
    return np.where(any_migrate, bin_starts[first_idx], np.nan)


def compute_t_migrate(hosts, decision="cost_sensitive", tau=None):
    out = pd.Series(index=hosts.index, dtype=float)
    for grp, g in hosts.groupby("model_grp"):
        bins = ttf_lookup[ttf_lookup["model_grp"] == grp].sort_values("bin_start_days")
        bin_starts = bins["bin_start_days"].values.astype(float)
        p_fail_row = bins["p_fail_within_window"].values.reshape(1, -1)
        ttf_row = bins["expected_ttf_days"].values.reshape(1, -1)
        cutoff_col = g["age_days"].values.reshape(-1, 1)
        valid = bin_starts.reshape(1, -1) < cutoff_col
        if decision == "cost_sensitive":
            fc = g["failure_cost_host"].values.reshape(-1, 1)
            mc = g["migration_cost_host"].values.reshape(-1, 1)
            migrate = cost_sensitive_decision(p_fail_row, ttf_row, fc, mc)["migrate"] & valid
        else:
            migrate = threshold_decision(p_fail_row, tau) & valid
        out.loc[g.index] = first_migrate_bin(migrate, bin_starts)
    return out


def classify_and_cost(hosts, t_migrate):
    migrated = t_migrate.notna()
    outcome = np.select(
        [hosts["failed"].eq(1) & migrated, hosts["failed"].eq(1) & ~migrated,
         hosts["failed"].eq(0) & migrated, hosts["failed"].eq(0) & ~migrated],
        ["necessary_migration", "customer_impacting_failure", "unnecessary_migration", "correct_inaction"],
        default="unknown",
    )
    cost = np.select(
        [outcome == "necessary_migration", outcome == "customer_impacting_failure", outcome == "unnecessary_migration"],
        [hosts["migration_cost_host"], hosts["failure_cost_host"], hosts["migration_cost_host"]],
        default=0.0,
    )
    return outcome, cost


def find_matched_tau(hosts, target_migrations):
    lo, hi = TAU, ttf_lookup["p_fail_within_window"].max()
    for _ in range(20):
        mid = (lo + hi) / 2
        n = compute_t_migrate(hosts, "threshold", mid).notna().sum()
        if n > target_migrations:
            lo = mid
        else:
            hi = mid
    n_lo = compute_t_migrate(hosts, "threshold", lo).notna().sum()
    n_hi = compute_t_migrate(hosts, "threshold", hi).notna().sum()
    return lo if abs(n_lo - target_migrations) <= abs(n_hi - target_migrations) else hi


results = []
for rho in RHO_VALUES:
    v = assign_vms_correlated(rho)
    achieved_corr = np.corrcoef(
        v["criticality_weight"].rank().values,
        v["host_id"].map(drv.set_index("host_id")["host_risk_score"]).rank().values,
    )[0, 1]
    hosts = build_hosts(v)

    t_cs = compute_t_migrate(hosts, "cost_sensitive")
    outcome_cs, cost_cs = classify_and_cost(hosts, t_cs)
    n_cs_migrations = t_cs.notna().sum()

    tau_matched = find_matched_tau(hosts, n_cs_migrations)
    t_th = compute_t_migrate(hosts, "threshold", tau_matched)
    outcome_th, cost_th = classify_and_cost(hosts, t_th)
    n_th_migrations = t_th.notna().sum()

    n_fail_cs = (outcome_cs == "customer_impacting_failure").sum()
    n_fail_th = (outcome_th == "customer_impacting_failure").sum()
    total_cost_cs, total_cost_th = cost_cs.sum(), cost_th.sum()
    advantage_pct = (total_cost_th - total_cost_cs) / total_cost_th  # positive = cost-sensitive wins

    results.append(dict(
        rho_target=rho, rho_achieved=achieved_corr,
        n_cs_migrations=n_cs_migrations, n_th_migrations=n_th_migrations, tau_matched=tau_matched,
        customer_impacting_failures_cs=n_fail_cs, customer_impacting_failures_th=n_fail_th,
        total_cost_cs=total_cost_cs, total_cost_th=total_cost_th,
        cost_sensitive_advantage_pct=advantage_pct,
    ))
    print(f"rho={rho:.1f} (achieved rank-corr={achieved_corr:.3f}): "
          f"migrations cs={n_cs_migrations} th={n_th_migrations} (tau={tau_matched:.5f}) | "
          f"missed-failures cs={n_fail_cs} th={n_fail_th} | "
          f"total_cost cs={total_cost_cs:.0f} th={total_cost_th:.0f} | "
          f"cost-sensitive advantage={advantage_pct:+.2%}")

results_df = pd.DataFrame(results)
results_df.to_csv(PROCESSED / "correlated_assignment_sweep.csv", index=False)
print(f"\nSaved -> data/processed/correlated_assignment_sweep.csv")

print("\n" + "=" * 78)
print("SUMMARY")
print("=" * 78)
print(results_df[["rho_target", "rho_achieved", "customer_impacting_failures_cs",
                   "customer_impacting_failures_th", "cost_sensitive_advantage_pct"]].to_string(index=False))

crossover = results_df[results_df["cost_sensitive_advantage_pct"] > 0]
if len(crossover) > 0:
    print(f"\nCost-sensitive policy overtakes the matched-budget threshold starting around "
          f"rho ~ {crossover['rho_achieved'].iloc[0]:.2f} rank-correlation between workload "
          f"criticality and host risk.")
else:
    print("\nCost-sensitive policy did not overtake the matched-budget threshold at any tested rho "
          "-- see task9_summary.md for what this implies.")

print("\nDone.")
