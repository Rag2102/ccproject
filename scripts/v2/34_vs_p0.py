"""Week 19 (ADR-005 consequence): every policy against never migrating (P0), descriptive.

P2 is tuned to use the budget, so it can cost more than doing nothing; a win over P2 does not by
itself show that a policy beats P0. ADR-005 requires every results table to show P0 and P3 next to
P2. This script gives, per (regime, budget, policy), the paired per-seed saving against P0,
S = (C_P0 - C) / C_P0 (positive: the policy costs less than never migrating), with its mean, a
95% BCa interval over seeds, and the share of seeds where the policy beats P0. Descriptive only:
not part of the confirmatory family, no multiplicity correction.

Writes results/summary/vs_p0.json (or results/small/summary/ with --small).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
SEED_BOOT = 20261004


def bca(x: np.ndarray) -> list[float]:
    if len(x) < 3 or np.allclose(x, x[0]):
        return [float(x.mean()), float(x.mean())]
    r = stats.bootstrap(
        (x,), np.mean, n_resamples=10_000, method="BCa", random_state=np.random.default_rng(SEED_BOOT)
    )
    return [float(r.confidence_interval.low), float(r.confidence_interval.high)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--small", action="store_true")
    ap.add_argument("--groups", nargs="+", default=["A", "E", "B", "C", "D"])
    a = ap.parse_args()
    res = ROOT / "results" / ("small" if a.small else "")
    raw, out = res / "raw", res / "summary"
    parts = [pd.read_parquet(f) for g in a.groups for f in sorted((raw / g).glob("*.parquet"))]
    if not parts:
        raise SystemExit(f"no collected cells under {raw}")
    d = pd.concat(parts, ignore_index=True)
    d = d[d.family == "eval"]
    p0 = d[d.policy == "P0"].set_index(["regime", "seed"])["total_cost"]
    cells = []
    for (reg, b, pol), g in d[d.policy != "P0"].groupby(["regime", "budget_pct", "policy"]):
        g = g.set_index("seed")
        base = p0.loc[reg].reindex(g.index)
        ok = base.notna() & (base > 0)
        s = ((base[ok] - g.total_cost[ok]) / base[ok]).to_numpy()
        if not len(s):
            continue
        cells.append(
            {
                "regime": reg,
                "budget_pct": float(b),
                "policy": pol,
                "n_seeds": int(len(s)),
                "saving_vs_p0_mean": float(s.mean()),
                "ci_bca": bca(s),
                "share_seeds_beating_p0": float((s > 0).mean()),
                "cost_ratio_to_p0_mean": float((g.total_cost[ok] / base[ok]).mean()),
            }
        )
    out.mkdir(parents=True, exist_ok=True)
    note = "S = (C_P0 - C) / C_P0 per seed; positive: cheaper than never migrating. Descriptive."
    (out / "vs_p0.json").write_text(json.dumps({"note": note, "cells": cells}, indent=1))
    print(f"{len(cells)} cells -> {(out / 'vs_p0.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
