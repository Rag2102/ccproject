"""Cost accounting and run outputs (plan Week 13; SIM_SPEC section 5, PROTOCOL section 4).

Cost is what happens in the run, in customer-impact minutes:
  interruption  c = w_tier x D_fail for every VM on a host when it fails (resident VMs one by
                one; transient VMs as drawn for that failure, identical for every policy);
  migration     m = w_tier x blackout + lambda_bw x duration, charged when a migration starts
                (a migration that never starts is free and its GB is refunded).
Only events at t in [warm-up, warm-up + horizon) are counted. No migration is credited with an
averted failure. "Necessary" (the source fails within H days of the start, while the VM would
still have been running) is a metric, never a credit.

Outputs per run: outcomes.parquet (one row per interruption, transient charge and migration),
daily.parquet, and summary.json with the git SHA, a hash of the configuration, seed and policy.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# migration status
DONE, FAILED_SRC, CANCELLED_DST, CANCELLED_DEPART, DROPPED = 0, 1, 2, 3, 4
STATUS = {
    DONE: "done",
    FAILED_SRC: "failed_source",
    CANCELLED_DST: "cancelled_destination",
    CANCELLED_DEPART: "cancelled_departed",
    DROPPED: "dropped",
}


def config_hash(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()[:16]


def git_sha() -> str:
    try:
        sha = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            text=True,
        ).stdout.strip()
    except OSError:
        sha, dirty = "", ""
    if not sha:  # a `git archive` build (clean container): the commit comes from the build
        env = os.environ.get("VMMBENCH_GIT_SHA")
        return f"{env}+archive" if env else "unknown"
    return sha + ("-dirty" if dirty else "")


@dataclass
class Ledger:
    """Append-only lists of events, turned into tables at the end of a run."""

    t0: float  # first counted time (end of warm-up), days
    t1: float  # end of the horizon, days
    interrupts: list = field(default_factory=list)  # (t, vm, host, tier, cost, in_flight)
    transients: list = field(default_factory=list)  # (t, host, n, cost)
    migrations: dict = field(default_factory=dict)  # column -> list of arrays
    daily: list = field(default_factory=list)

    def counted(self, t: float) -> bool:
        return self.t0 <= t < self.t1

    def interrupt(self, t, vm, host, tier, cost, in_flight=False):
        self.interrupts.append((t, int(vm), int(host), int(tier), float(cost), bool(in_flight)))

    def transient(self, t, host, n, cost):
        self.transients.append((t, int(host), int(n), float(cost)))

    def add_migrations(self, **cols: np.ndarray) -> np.ndarray:
        """Append a batch; returns their migration ids."""
        n0 = len(self.migrations.get("vm", []))
        for k, v in cols.items():
            self.migrations.setdefault(k, []).extend(np.asarray(v).tolist())
        return np.arange(n0, n0 + len(cols["vm"]))

    def set_status(self, mig_id: int, status: int, t: float | None = None):
        self.migrations["status"][mig_id] = status
        if t is not None:
            self.migrations["t_stop"][mig_id] = t

    # ------------------------------------------------------------------ tables
    def tables(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        it = pd.DataFrame(
            self.interrupts, columns=["t", "vm", "host", "tier", "cost", "in_flight"]
        ).assign(kind="interrupt")
        tr = pd.DataFrame(self.transients, columns=["t", "host", "n", "cost"]).assign(
            kind="transient"
        )
        mg = pd.DataFrame(self.migrations) if self.migrations else pd.DataFrame()
        if len(mg):
            mg = mg.rename(columns={"t_start": "t"}).assign(kind="migration")
            mg["status"] = mg["status"].map(STATUS)
        return it, tr, mg

    def summarise(self, mg_extra: pd.DataFrame | None = None) -> tuple[dict, pd.DataFrame]:
        it, tr, mg = self.tables()
        if mg_extra is not None and len(mg):
            mg = mg.join(mg_extra)
        c_it = it[it["t"].between(self.t0, self.t1, inclusive="left")]
        c_tr = tr[tr["t"].between(self.t0, self.t1, inclusive="left")]
        if len(mg):
            started = mg["status"] != STATUS[DROPPED]
            c_mg = mg[started & mg["t"].between(self.t0, self.t1, inclusive="left")]
        else:
            c_mg = mg
        daily = pd.DataFrame(self.daily)
        dc = daily[daily["day"].between(self.t0, self.t1 - 1)] if len(daily) else daily
        budget = float(dc["budget_gb"].sum()) if len(dc) else 0.0
        gb = float(c_mg["gb"].sum()) if len(c_mg) else 0.0
        out = {
            "cost_total": float(c_it["cost"].sum() + c_tr["cost"].sum())
            + (float(c_mg["cost"].sum()) if len(c_mg) else 0.0),
            "cost_interrupt_resident": float(c_it["cost"].sum()),
            "cost_interrupt_transient": float(c_tr["cost"].sum()),
            "cost_migration": float(c_mg["cost"].sum()) if len(c_mg) else 0.0,
            "cost_resident_plus_migration": float(c_it["cost"].sum())
            + (float(c_mg["cost"].sum()) if len(c_mg) else 0.0),
            "interrupted_vms": int(len(c_it)),
            "interrupted_in_flight": int(c_it["in_flight"].sum()) if len(c_it) else 0,
            "interrupted_transient_vms": int(c_tr["n"].sum()) if len(c_tr) else 0,
            "host_failures": int(len(c_tr)),
            "migrations": int(len(c_mg)),
            "migrations_done": int((c_mg["status"] == STATUS[DONE]).sum()) if len(c_mg) else 0,
            "migrations_necessary": int(c_mg["necessary"].sum())
            if len(c_mg) and "necessary" in c_mg
            else 0,
            "gb_migrated": gb,
            "budget_gb": budget,
            "budget_utilisation": gb / budget if budget > 0 else 0.0,
            "rejected_arrivals": int(dc["rejected"].sum()) if len(dc) else 0,
            "max_daily_overspend_gb": float((dc["gb_planned"] - dc["budget_gb"]).max())
            if len(dc)
            else 0.0,
        }
        if len(c_mg):
            out["migrations_unnecessary"] = out["migrations"] - out["migrations_necessary"]
        return out, mg

    def write(self, out_dir: Path, meta: dict, summary: dict, mg: pd.DataFrame) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        it, tr, _ = self.tables()
        outcomes = pd.concat([it, tr, mg], ignore_index=True, sort=False)
        outcomes.to_parquet(out_dir / "outcomes.parquet", index=False)
        pd.DataFrame(self.daily).to_parquet(out_dir / "daily.parquet", index=False)
        (out_dir / "summary.json").write_text(
            json.dumps({**meta, **summary}, indent=2, sort_keys=True)
        )
