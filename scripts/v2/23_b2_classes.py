"""Regime B2 inputs (PROTOCOL section 3; SIM_SPEC section 8): tier mix per host class, measured.

Host class = machine platform (Google 2019, cells a, b, h; windows days 8-14, 15-21, 22-28). For
each platform: its share of machines, its long-removal rate per machine-day (the G1 primary
proxy, from events before each window) and the M1 tier mix of its placements (placement-weighted,
like the G1 estimate). Pooled with equal weight per cell and window. Platforms with fewer than 30
machines in a window are left out of that window (as in 13b_trace_strata.py).

Writes results/v2/b2_classes.json: classes ordered from lowest to highest risk.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("tr", ROOT / "scripts/v2/13_trace_rho.py")
tr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tr)

MIN_MACHINES = 30


def main() -> None:
    parts = []
    for cell in tr.CELLS:
        d = tr.GOOGLE / f"cell_{cell}"
        pl = pd.read_parquet(d / "placements.parquet")
        risk = pd.read_parquet(d / "risk.parquet")
        for w, g in pl.groupby("window"):
            g = g.assign(tier=tr.mappings(g["tier5"].to_numpy(), g["sc"].to_numpy())["M1"])
            rk = risk[risk["window"] == w][["machine_id", "platform", "risk_platform"]]
            g = g.merge(rk, on="machine_id", how="inner")
            n_mach = rk.groupby("platform")["machine_id"].nunique()
            keep = n_mach[n_mach >= MIN_MACHINES].index
            mix = (
                g[g["platform"].isin(keep)]
                .pivot_table(index="platform", columns="tier", values="n", aggfunc="sum")
                .reindex(columns=[0, 1, 2])
                .fillna(0)
            )
            mix = mix.div(mix.sum(axis=1), axis=0)
            rate = rk.groupby("platform")["risk_platform"].first()
            share = n_mach[keep] / n_mach[keep].sum()
            for p in mix.index:
                parts.append(
                    {
                        "cell": cell,
                        "window": int(w),
                        "platform": p,
                        "machine_share": float(share[p]),
                        "risk": float(rate[p]),
                        "tier_mix": mix.loc[p].to_numpy(float),
                    }
                )
    df = pd.DataFrame(parts)
    n_cw = df.groupby(["cell", "window"]).ngroups
    out = []
    for p, g in df.groupby("platform"):
        # equal weight per (cell, window); a platform missing from one counts as share 0 there
        share = g["machine_share"].sum() / n_cw
        w = g["machine_share"].to_numpy()
        out.append(
            {
                "platform": p,
                "machine_share": float(share),
                "risk_per_machine_day": float(np.average(g["risk"], weights=w)),
                "tier_mix_low_med_high": np.average(np.vstack(g["tier_mix"]), axis=0, weights=w)
                .round(6)
                .tolist(),
                "present_in": int(len(g)),
            }
        )
    out.sort(key=lambda r: r["risk_per_machine_day"])
    tot = sum(r["machine_share"] for r in out)
    for r in out:
        r["machine_share"] = round(r["machine_share"] / tot, 6)
    res = {
        "source": "Google 2019 cells a, b, h; windows 2-4; M1 mapping; platform long-removal rate",
        "min_machines": MIN_MACHINES,
        "classes": out,
    }
    (ROOT / "results" / "v2" / "b2_classes.json").write_text(json.dumps(res, indent=2))
    for r in out:
        print(r)


if __name__ == "__main__":
    main()
