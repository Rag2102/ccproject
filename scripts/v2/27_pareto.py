"""Week 19: Pareto frontiers per regime and figure F5 (PROTOCOL.md v1.0 section 9).

From the collected cells (results/raw/<group>/*.parquet), per regime and policy, means over eval
seeds at each budget:
  frontier 1   missed failures (VMs interrupted) against migrations, budgets 0.5-5% (P0 at 0)
  frontier 2   total cost against budget
  area         area under each policy's total-cost-vs-budget curve over the four budgets
               (trapezoid in log budget), divided by P0's cost times the log-budget range, so
               1.0 means "as costly as never migrating at every budget"; lower is better
Writes results/summary/pareto.json and results/figures/v2_F5_pareto.pdf.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
COLORS = {
    "P0": "#888888", "P1": "#c9a227", "P2": "#e0571f", "P3": "#8c6bb1", "P4": "#12a150",
    "P5": "#2563eb", "P6": "#0e9f9a", "P7": "#111111", "P8": "#bbbbbb",
}  # fmt: skip


def load(root: Path, groups: list[str]) -> pd.DataFrame:
    parts = [pd.read_parquet(f) for g in groups for f in sorted((root / g).glob("*.parquet"))]
    if not parts:
        raise SystemExit(f"no collected cells under {root}")
    return pd.concat(parts, ignore_index=True)


def frontiers(d: pd.DataFrame) -> dict:
    out = {}
    for regime, g in d.groupby("regime"):
        p0 = g[g.policy == "P0"]
        c0 = float(p0["total_cost"].mean()) if len(p0) else np.nan
        pts, areas = {}, {}
        for pol, h in g.groupby("policy"):
            m = h.groupby("budget_pct")[["migrations", "missed_failures", "total_cost"]].mean()
            pts[pol] = {str(b): {k: float(v) for k, v in row.items()} for b, row in m.iterrows()}
            if pol != "P0" and len(m) > 1 and np.isfinite(c0) and c0 > 0:
                lb = np.log(m.index.to_numpy(float))
                areas[pol] = float(
                    np.trapezoid(m["total_cost"].to_numpy(), lb) / (c0 * (lb[-1] - lb[0]))
                )
        out[regime] = {"p0_cost": c0, "points": pts, "normalised_area": areas}
    return out


def figure(res: dict, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    regs = list(res)
    fig, ax = plt.subplots(2, len(regs), figsize=(3.2 * len(regs), 6.2), squeeze=False)
    for j, r in enumerate(regs):
        for pol, pts in res[r]["points"].items():
            bs = sorted(pts, key=float)
            mig = [pts[b]["migrations"] for b in bs]
            miss = [pts[b]["missed_failures"] for b in bs]
            cost = [pts[b]["total_cost"] for b in bs]
            col = COLORS.get(pol, "#555555")
            ax[0, j].plot(mig, miss, "-o", ms=3, lw=1.3, color=col, label=pol)
            if pol != "P0":
                ax[1, j].plot(
                    [float(b) for b in bs], cost, "-o", ms=3, lw=1.3, color=col, label=pol
                )
        if np.isfinite(res[r]["p0_cost"]):
            ax[1, j].axhline(res[r]["p0_cost"], color=COLORS["P0"], ls=":", lw=1)
        ax[0, j].set(title=r, xlabel="migrations", ylabel="missed failures (VMs)" if j == 0 else "")
        ax[0, j].set_xscale("symlog")
        ax[1, j].set(xlabel="budget (% memory / day)", ylabel="total cost" if j == 0 else "")
        ax[1, j].set_xscale("log")
    ax[0, 0].legend(fontsize=6, ncol=2)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--groups", nargs="+", default=["A", "E", "B", "C", "D"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    root = ROOT / "results" / ("dryrun" if a.dry_run else "raw")
    out = ROOT / "results" / ("dryrun_summary" if a.dry_run else "summary")
    out.mkdir(parents=True, exist_ok=True)
    groups = [g for g in a.groups if (root / g).exists()]
    res = frontiers(load(root, groups))
    (out / "pareto.json").write_text(json.dumps(res, indent=1))
    figure(
        res,
        ROOT
        / "results"
        / "figures"
        / ("v2_F5_pareto_dryrun.pdf" if a.dry_run else "v2_F5_pareto.pdf"),
    )
    print({r: {p: round(v, 3) for p, v in x["normalised_area"].items()} for r, x in res.items()})


if __name__ == "__main__":
    main()
