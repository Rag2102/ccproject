"""Day 2 (1 Nov 2026): re-read THEORY.md section 4's direction checks on the final result files.

Reads results/summary/A.json, E.json and results/v2/f4_theory_params.json; runs nothing in the
simulator. Writes results/summary/theory_reread.json.

  .venv/bin/python scripts/v2/53_theory_reread.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmsim import theory  # noqa: E402

BUDGETS = (0.5, 1.0, 2.0, 5.0)
A = [f"A{i}" for i in range(1, 8)]
E = ["E1", "E2", "E3"]


def main() -> None:
    cells = []
    for g in "AE":
        cells += json.loads((ROOT / f"results/summary/{g}.json").read_text())["cells"]
    sim = {(c["regime"], c["budget_pct"]): c for c in cells if c["policy"] == "P4"}
    par = json.loads((ROOT / "results/v2/f4_theory_params.json").read_text())
    rows = []
    for (reg, b), c in sorted(sim.items()):
        p = par[reg]
        q = min(1.0, 30 * b / 100)  # as F4: a daily budget over the 30-day horizon
        cf = theory.delta(theory.Model(rho=p["rho"], s_y=p["s_y"], s_x=p["s_x"], mu_x=p["mu_x"], q=q, lam=p["lam"]))
        rows.append({"regime": reg, "budget_pct": b, "closed_form": cf, "simulator": c["delta_mean"],
                     "ci_bca": c["ci_bca"], "gap_points": (c["delta_mean"] - cf) * 100})  # fmt: skip
    d = {(r["regime"], r["budget_pct"]): r for r in rows}
    out = {
        "all_positive_beyond_ci": all(r["ci_bca"][0] > 0 for r in rows),
        "n_cells": len(rows),
        "falls_with_rho": {str(b): all(d[(x, b)]["simulator"] > d[(y, b)]["simulator"]
                                       for x, y in zip(A[:-1], A[1:], strict=True)) for b in BUDGETS},  # fmt: skip
        "rises_with_spread": {str(b): all(d[(x, b)]["simulator"] < d[(y, b)]["simulator"]
                                          for x, y in zip(E[:-1], E[1:], strict=True)) for b in BUDGETS},  # fmt: skip
        "gap_points_min": min(r["gap_points"] for r in rows),
        "gap_points_max": max(r["gap_points"] for r in rows),
        "rows": rows,
    }
    (ROOT / "results/summary/theory_reread.json").write_text(json.dumps(out, indent=1))
    print({k: v for k, v in out.items() if k != "rows"})
    print([(r["regime"], r["budget_pct"], round(r["closed_form"] * 100, 1), round(r["simulator"] * 100, 1)) for r in rows if r["budget_pct"] == 2.0])


if __name__ == "__main__":
    main()
