"""v1 regression (gate G2, criterion 3; SIM_SPEC section 14).

v1's setting: every Backblaze drive (2013-2017, >= 1.5 TB) is a host with its own age clock;
the 2,013,767 Azure VMs are placed on hosts uniformly at random once (v1's draw, seed 42) and
never leave; decisions are per host at 30-day age bins; a host is migrated at most once.

Every number below is computed with vmsim's own pieces: per-VM costs from `migration`
(v1_closed_form) and `CostConfig`, the v1 rule's urgency from `policies.reference`, and
realised-cost accounting. With static VMs, realised accounting is v1's accounting: a VM moved
off a host that fails later is safe, because it never leaves its new host and nothing arrives
on the old one. The v2 engine differs from v1 by adding VM churn (arrivals and departures),
which is the intended change (PROTOCOL section 4, rules 1 and 2).

The event loop itself is not used here (v1's hosts each have their own clock over up to five
years, which the engine's shared calendar does not represent); it is validated by the analytic,
self-calibration and invariant checks.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from vmsim import migration
from vmsim.config import CostConfig, MigrationConfig
from vmsim.entities import all_v1_vms, v1_drive_table
from vmsim.failure import V1_LOOKUP
from vmsim.policies.reference import urgency

V1_SEED = 42
V1_TARGETS = {"cost_sensitive": 456_533, "threshold_matched": 442_701}
V1_MIGRATIONS = {"cost_sensitive": 5_116, "threshold_matched": 5_522}


def host_table() -> tuple[pd.DataFrame, pd.DataFrame]:
    drv = v1_drive_table().copy()
    lookup = pd.read_csv(V1_LOOKUP)
    top = sorted(lookup.loc[lookup["model_grp"] != "OTHER", "model_grp"].unique())
    drv["host_id"] = np.arange(len(drv))
    drv["model_grp"] = np.where(drv["model"].isin(top), drv["model"], "OTHER")

    vms = all_v1_vms()
    mc, cc = MigrationConfig(v1_closed_form=True), CostConfig()
    w = np.asarray(cc.tier_weights)[vms.tier]
    dur, blk, _ = migration.precopy(
        vms.mem_gb, migration.dirty_mbps(vms.avg_cpu, mc), migration.host_bw_mbps(mc), mc
    )
    m = migration.migration_cost_min(w, dur, blk, cc)
    c = w * cc.d_fail_min
    host = np.random.default_rng(V1_SEED).integers(0, len(drv), size=len(vms))
    n = len(drv)
    drv["F"] = np.bincount(host, weights=c, minlength=n)
    drv["M"] = np.bincount(host, weights=m, minlength=n)
    drv["n_vms"] = np.bincount(host, minlength=n)
    return drv, lookup


def first_bin(hosts: pd.DataFrame, lookup: pd.DataFrame, rule) -> np.ndarray:
    """Age (days) of the first 30-day bin at which `rule` migrates each host, or NaN."""
    out = np.full(len(hosts), np.nan)
    for grp, g in hosts.groupby("model_grp"):
        b = lookup[lookup["model_grp"] == grp].sort_values("bin_start_days")
        starts = b["bin_start_days"].to_numpy(float)
        p = b["p_fail_within_window"].to_numpy()[None, :]
        ttf = b["expected_ttf_days"].to_numpy()[None, :]
        valid = starts[None, :] < g["age_days"].to_numpy()[:, None]
        mig = rule(p, ttf, g) & valid
        any_ = mig.any(axis=1)
        out[g.index.to_numpy()] = np.where(any_, starts[mig.argmax(axis=1)], np.nan)
    return out


def realised_cost(hosts: pd.DataFrame, t_mig: np.ndarray) -> dict:
    migrated = ~np.isnan(t_mig)
    failed = hosts["failed"].to_numpy() == 1
    cost = np.where(migrated, hosts["M"], np.where(failed, hosts["F"], 0.0))
    return {
        "cost": float(cost.sum()),
        "migrations": int(migrated.sum()),
        "necessary": int((migrated & failed).sum()),
        "missed_failures": int((~migrated & failed).sum()),
    }


def run() -> dict:
    hosts, lookup = host_table()
    tau95 = float(lookup["p_fail_within_window"].quantile(0.95))

    def p3(p, ttf, g):
        F = g["F"].to_numpy()[:, None]
        M = g["M"].to_numpy()[:, None]
        return p * F * urgency(ttf, 30) > M

    def thr(tau):
        return lambda p, ttf, g: np.broadcast_to(p > tau, (len(g), p.shape[1]))

    cs = realised_cost(hosts, first_bin(hosts, lookup, p3))
    naive = realised_cost(hosts, first_bin(hosts, lookup, thr(tau95)))
    # v1's matched budget: bisection on tau for the cost-sensitive policy's migration count
    target = cs["migrations"]
    lo, hi = tau95, float(lookup["p_fail_within_window"].max())
    for _ in range(25):
        mid = (lo + hi) / 2
        if realised_cost(hosts, first_bin(hosts, lookup, thr(mid)))["migrations"] > target:
            lo = mid
        else:
            hi = mid
    r_lo = realised_cost(hosts, first_bin(hosts, lookup, thr(lo)))
    r_hi = realised_cost(hosts, first_bin(hosts, lookup, thr(hi)))
    matched = r_lo if abs(r_lo["migrations"] - target) <= abs(r_hi["migrations"] - target) else r_hi
    out = {
        "hosts": len(hosts),
        "vms": int(hosts["n_vms"].sum()),
        "tau95": tau95,
        "cost_sensitive": cs,
        "threshold_naive": naive,
        "threshold_matched": matched,
    }
    for k, target_cost in V1_TARGETS.items():
        out[k]["v1_cost"] = target_cost
        out[k]["rel_diff"] = out[k]["cost"] / target_cost - 1
        out[k]["v1_migrations"] = V1_MIGRATIONS[k]
    out["delta_cs_vs_matched"] = (matched["cost"] - cs["cost"]) / matched["cost"]
    out["pass"] = all(abs(out[k]["rel_diff"]) <= 0.01 for k in V1_TARGETS)
    return out
