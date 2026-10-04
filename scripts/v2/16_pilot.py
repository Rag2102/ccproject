"""Week 14: pilot timing, SD of Delta, and the smoke grid (PROTOCOL sections 5-6).

For each regime cell and budget: tune P2 (tau and within-host order) on dev seeds 101-110, by
the protocol's budget criterion (P2) and by cost (P2c, proposed; vmsim/policies/tune.py), then
run P0, P1, P2, P2c, P3, P7 and P8 on pilot seeds 201-205 (pilot seeds are used here only, then
discarded). Reports per-run wall time, Delta vs P2 = (C_P2 - C_pi) / C_P2 per seed, its SD
(the protocol's power rule uses SD of P3 vs P2), and benefit captured (C_P0 - C_pi) /
(C_P0 - C_P7). The smoke grid is the same table and is for debugging only: no claim rests on it.

Writes results/v2/pilot_w14.json and results/v2/pilot_w14_runs.csv.

Run from the repository root:
  .venv/bin/python scripts/v2/16_pilot.py --hosts 2000 --cells A1 A3 --budgets 0.02
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmsim import engine, scenarios, worlds  # noqa: E402
from vmsim.config import SimConfig  # noqa: E402
from vmsim.policies import reference as R  # noqa: E402
from vmsim.policies.tune import DEV_SEEDS, tune_p2  # noqa: E402

PILOT_SEEDS = tuple(range(201, 206))
OUT = ROOT / "results" / "v2"


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hosts", type=int, default=2_000)
    ap.add_argument("--horizon", type=int, default=365)
    ap.add_argument("--cells", nargs="+", default=["A1", "A3"])
    ap.add_argument("--budgets", nargs="+", type=float, default=[0.02])
    ap.add_argument("--dev-seeds", type=int, default=len(DEV_SEEDS))
    ap.add_argument("--out", default="pilot_w14", help="output name in results/v2")
    args = ap.parse_args()

    base = SimConfig(n_hosts=args.hosts, horizon_days=args.horizon, name="pilot")
    rows, tuned = [], {}
    for cell in args.cells:
        cfg = scenarios.regime(base, cell)
        t = time.time()
        dev = [engine.prepare(worlds.generate(cfg, s), cfg) for s in DEV_SEEDS[: args.dev_seeds]]
        pil = [engine.prepare(worlds.generate(cfg, s), cfg) for s in PILOT_SEEDS]
        log(f"{cell}: worlds ready in {time.time() - t:.0f}s (rho target {cfg.placement.rho})")
        for b in args.budgets:
            t = time.time()
            tp = tune_p2(dev, b, criterion="budget")
            tc = tune_p2(dev, b, criterion="cost")
            tuned[f"{cell}@{b}"] = {"budget": tp, "cost": tc}
            log(
                f"{cell} @ {b:.1%}: P2 (budget) tau={tp['tau']:.2e} {tp['order']}; "
                f"P2c (cost) tau={tc['tau']:.2e} {tc['order']} ({time.time() - t:.0f}s)"
            )
            pols = [
                R.Never(),
                R.Threshold(),
                R.Threshold(tp["tau"], tp["order"], "P2"),
                R.Threshold(tc["tau"], tc["order"], "P2c"),
                R.V1Rule(),
                R.Oracle(),
                R.RandomPick(),
            ]
            for prep in pil:
                for pol in pols:
                    s = engine.run(prep, pol, budget_frac=b)
                    rows.append({"cell": cell, "budget": b, **s})
            log(f"{cell} @ {b:.1%}: pilot runs done")

    runs = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    runs.to_csv(OUT / f"{args.out}_runs.csv", index=False)
    summary = {
        "hosts": args.hosts,
        "horizon": args.horizon,
        "pilot_seeds": PILOT_SEEDS,
        "dev_seeds": DEV_SEEDS[: args.dev_seeds],
        "p2": tuned,
        "cells": {},
    }
    for (cell, b), g in runs.groupby(["cell", "budget"]):
        c = g.pivot(index="seed", columns="policy", values="cost_total")
        delta = {p: ((c["P2"] - c[p]) / c["P2"]) for p in c.columns if p != "P2"}
        delta_c = {p: ((c["P2c"] - c[p]) / c["P2c"]) for p in c.columns if p != "P2c"}
        captured = {p: ((c["P0"] - c[p]) / (c["P0"] - c["P7"])) for p in c.columns}
        summary["cells"][f"{cell}@{b}"] = {
            "mean_cost": c.mean().round(1).to_dict(),
            "delta_vs_p2_mean": {p: float(v.mean()) for p, v in delta.items()},
            "delta_vs_p2_sd": {p: float(v.std(ddof=1)) for p, v in delta.items()},
            "delta_vs_p2c_mean": {p: float(v.mean()) for p, v in delta_c.items()},
            "delta_vs_p2c_sd": {p: float(v.std(ddof=1)) for p, v in delta_c.items()},
            "benefit_captured_mean": {p: float(v.mean()) for p, v in captured.items()},
            "budget_utilisation": g.groupby("policy")["budget_utilisation"].mean().to_dict(),
            "wall_s_mean": g.groupby("policy")["wall_s"].mean().round(2).to_dict(),
            # per policy: migrations move VMs to safer hosts and lower the correlation
            "rho_tier_risk_horizon": g.groupby("policy")["rho_tier_risk_horizon"]
            .mean()
            .round(3)
            .to_dict(),
            "p7_le_all": bool(all((c["P7"] <= c[p] + 1e-9).all() for p in c.columns)),
            "p8_ge_p2_mean": bool(c["P8"].mean() >= c["P2"].mean()),
        }
        log(
            f"{cell} @ {b:.1%}: SD(Delta P3 vs P2) = {np.std(delta['P3'], ddof=1):.4f}; "
            f"vs P2c = {np.std(delta_c['P3'], ddof=1):.4f}"
        )
    (OUT / f"{args.out}.json").write_text(json.dumps(summary, indent=2, default=float))
    log(f"wrote results/v2/{args.out}.json")


if __name__ == "__main__":
    main()
