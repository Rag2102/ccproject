"""
The exact same correlation-sweep simulation as
scripts/07_correlated_assignment_experiment.py, refactored into two plain
functions -- load_data() and simulate_one(data, rho, seed) -- so a single
(rho, seed) trial can run as one independent AWS Lambda invocation.

This is a deliberate refactor, not a rewrite: every line of actual modeling
logic (assign_vms_correlated, build_hosts, compute_t_migrate,
classify_and_cost) is copied unchanged from the original script. See
cloud/sim/README.md and docs/cloud_architecture.md for how this is verified
to reproduce script 07's own numbers exactly at rho in {0.0, 0.3, 0.6, 0.9}
before trusting the new, finer sweep this enables.

The one deliberate improvement over the original script: RHO_VALUES there
was only 4 points with a single seed each (no way to tell noise from signal
in the "where does the advantage appear" question). Distributing the work
makes a finer sweep with multiple seeds per rho cheap, so cloud/infra's
Step Functions state machine fans out over RHO_VALUES x SEEDS (see
cloud/sim/driver_config.py) instead of just the original 4 points.
"""
from pathlib import Path

import numpy as np
import pandas as pd

# scripts/policy.py has zero dependencies beyond numpy (see webapp/core.py's
# same reasoning) -- bundled directly into the worker image rather than
# pulling in the rest of scripts/.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from policy import cost_sensitive_decision, threshold_decision  # noqa: E402

DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"


def load_data(data_dir=None):
    """Loads exactly what 07_correlated_assignment_experiment.py loads at
    module level. Call this once per Lambda container (module-level cache in
    the handler) -- it's the expensive part (the 198MB VM table)."""
    data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR

    drv = pd.read_csv(data_dir / "backblaze_drives_clean.csv").dropna(subset=["age_days"]).reset_index(drop=True)
    ttf_lookup = pd.read_csv(data_dir / "ttf_lookup_table.csv")
    top_models = sorted(ttf_lookup.loc[ttf_lookup["model_grp"] != "OTHER", "model_grp"].unique())
    drv["host_id"] = np.arange(len(drv))
    drv["model_grp"] = np.where(drv["model"].isin(top_models), drv["model"], "OTHER")

    vm = pd.read_csv(data_dir / "azure_vms_with_costs.csv.gz").copy()
    vm["total_migration_cost_min"] = vm["migration_resource_cost_min"] + vm["migration_customer_cost_min"]

    # Host risk score used ONLY to induce the correlation (a static
    # per-model-group summary of real hazard), not used inside the actual
    # decision logic, which still runs on the full dynamic
    # p_fail_within_window/TTF as before.
    host_risk = ttf_lookup.groupby("model_grp")["p_fail_within_window"].mean().rename("host_risk_score")
    drv = drv.merge(host_risk, on="model_grp", how="left")

    tau = ttf_lookup["p_fail_within_window"].quantile(0.95)

    return {"drv": drv, "ttf_lookup": ttf_lookup, "vm": vm, "tau": float(tau)}


def assign_vms_correlated(data, rho, seed):
    drv, vm = data["drv"], data["vm"]
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


def build_hosts(data, v):
    drv = data["drv"]
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


def compute_t_migrate(data, hosts, decision="cost_sensitive", tau=None):
    ttf_lookup = data["ttf_lookup"]
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


def find_matched_tau(data, hosts, target_migrations):
    ttf_lookup = data["ttf_lookup"]
    lo, hi = data["tau"], ttf_lookup["p_fail_within_window"].max()
    for _ in range(20):
        mid = (lo + hi) / 2
        n = compute_t_migrate(data, hosts, "threshold", mid).notna().sum()
        if n > target_migrations:
            lo = mid
        else:
            hi = mid
    n_lo = compute_t_migrate(data, hosts, "threshold", lo).notna().sum()
    n_hi = compute_t_migrate(data, hosts, "threshold", hi).notna().sum()
    return lo if abs(n_lo - target_migrations) <= abs(n_hi - target_migrations) else hi


def simulate_one(data, rho, seed):
    """One independent trial -- exactly script 07's per-rho loop body, for a
    single (rho, seed) pair. This is the unit of work one Lambda invocation
    does."""
    drv = data["drv"]
    v = assign_vms_correlated(data, rho, seed)
    achieved_corr = float(np.corrcoef(
        v["criticality_weight"].rank().values,
        v["host_id"].map(drv.set_index("host_id")["host_risk_score"]).rank().values,
    )[0, 1])
    hosts = build_hosts(data, v)

    t_cs = compute_t_migrate(data, hosts, "cost_sensitive")
    outcome_cs, cost_cs = classify_and_cost(hosts, t_cs)
    n_cs_migrations = int(t_cs.notna().sum())

    tau_matched = find_matched_tau(data, hosts, n_cs_migrations)
    t_th = compute_t_migrate(data, hosts, "threshold", tau_matched)
    outcome_th, cost_th = classify_and_cost(hosts, t_th)
    n_th_migrations = int(t_th.notna().sum())

    n_fail_cs = int((outcome_cs == "customer_impacting_failure").sum())
    n_fail_th = int((outcome_th == "customer_impacting_failure").sum())
    total_cost_cs, total_cost_th = float(cost_cs.sum()), float(cost_th.sum())
    advantage_pct = (total_cost_th - total_cost_cs) / total_cost_th  # positive = cost-sensitive wins

    return {
        "rho_target": rho, "seed": seed, "rho_achieved": achieved_corr,
        "n_cs_migrations": n_cs_migrations, "n_th_migrations": n_th_migrations,
        "tau_matched": float(tau_matched),
        "customer_impacting_failures_cs": n_fail_cs, "customer_impacting_failures_th": n_fail_th,
        "total_cost_cs": total_cost_cs, "total_cost_th": total_cost_th,
        "cost_sensitive_advantage_pct": float(advantage_pct),
    }
