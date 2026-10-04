"""Week 8 follow-up: within-platform correlation and removal counts (G1_decision.md, open items).

rho_definition.md promises tau-b within platform next to the pooled value, because platform mix
could confound age and risk. The primary proxy (platform rate) is constant within a platform,
so the within-platform statistic uses the per-machine proxy (shrunk long-removal rate). For each
cell, window and platform: tau-b between the M1 tier score and the machine's risk; combined over
platforms weighted by placements, then averaged over windows like the pooled estimate. 95%
percentile interval from 1,000 bootstrap resamples of machines.

Also counts, per cell, the removals behind the proxies (known before the last window starts).

Reads data/v2/google/cell_*/{placements,risk}.parquet (written by 13_trace_rho.py);
writes results/v2/trace_strata.json.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("tr", ROOT / "scripts/v2/13_trace_rho.py")
tr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tr)

N_BOOT = 1_000
MIN_MACHINES = 30  # platforms with fewer machines in a window are left out of that window


def strata_data(pl: pd.DataFrame, risk: pd.DataFrame) -> dict:
    """window -> list of (counts per machine x 3 tiers, risk level index, n levels, machine ids)."""
    out = {}
    for w, g in pl.groupby("window"):
        g = g.assign(score=tr.mappings(g["tier5"].to_numpy(), g["sc"].to_numpy())["M1"])
        cnt = g.pivot_table(index="machine_id", columns="score", values="n", aggfunc="sum")
        cnt = cnt.reindex(columns=[0, 1, 2]).fillna(0)
        rk = risk[risk["window"] == w].set_index("machine_id")[["platform", "risk_machine"]]
        cnt = cnt.join(rk, how="inner")
        parts = []
        for _, s in cnt.groupby("platform"):
            if len(s) < MIN_MACHINES:
                continue
            levels, idx = np.unique(s["risk_machine"].to_numpy(), return_inverse=True)
            parts.append((s[[0, 1, 2]].to_numpy(float), idx, len(levels), s.index.to_numpy()))
        out[int(w)] = parts
    return out


def stratified(data: dict, mult: dict | None = None) -> float:
    vals = []
    for w, parts in data.items():
        num = den = 0.0
        for k, (cnt, idx, n, _) in enumerate(parts):
            c = cnt if mult is None else cnt * mult[w][k][:, None]
            tab = np.vstack([np.bincount(idx, weights=c[:, j], minlength=n) for j in range(3)])
            t = tr.tau_b(tab)
            if np.isfinite(t):
                num += t * tab.sum()
                den += tab.sum()
        vals.append(num / den if den else np.nan)
    return float(np.nanmean(vals))


def main() -> None:
    rng = np.random.default_rng(tr.SEED)
    res = {}
    for cell in tr.CELLS:
        out = tr.GOOGLE / f"cell_{cell}"
        pl = pd.read_parquet(out / "placements.parquet")
        risk = pd.read_parquet(out / "risk.parquet")
        data = strata_data(pl, risk)
        ms = np.unique(np.concatenate([p[3] for parts in data.values() for p in parts]))
        pos = {w: [np.searchsorted(ms, p[3]) for p in parts] for w, parts in data.items()}
        est = stratified(data)
        reps = np.empty(N_BOOT)
        for b in range(N_BOOT):
            m = np.bincount(rng.integers(0, len(ms), len(ms)), minlength=len(ms)).astype(float)
            reps[b] = stratified(data, {w: [m[q] for q in ps] for w, ps in pos.items()})
        last = risk[risk["window"] == max(tr.WINDOWS)]
        res[cell] = {
            "tau_b_within_platform": round(est, 4),
            "ci95": [
                round(float(np.quantile(reps, 0.025)), 4),
                round(float(np.quantile(reps, 0.975)), 4),
            ],
            "platforms_used": {int(w): len(p) for w, p in data.items()},
            "machines": int(len(ms)),
            "removals_before_last_window": int(last["removals"].sum()),
            "long_removals_before_last_window": int(last["long_removals"].sum()),
            "machine_days_before_last_window": round(float(last["up_days"].sum()), 1),
        }
        print(cell, res[cell], flush=True)
    (ROOT / "results" / "v2" / "trace_strata.json").write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
