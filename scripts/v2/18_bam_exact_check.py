"""Week 15, task 3: BAM's greedy against the exact 0-1 knapsack, with GB weights.

Instances of up to 200 VMs, from two sources:
  sim    snapshots of the simulator's daily observation (regimes A3 and C, days 40-160, dev
         seeds), b_i = p c e - m at queue position 0, w = GB, from the VMs with b > 0 (a
         random 200 if more); budget = the cluster's daily budget scaled to the instance
         (share of the candidates' GB), so that it binds;
  synth  random instances with log-normal b and w and a budget of 10-50% of the total GB.
Greedy: density order, skip items that do not fit, continue (the engine's rule). Exact:
scipy.optimize.milp (HiGHS). The gap is (OPT - greedy) / OPT. The queue-dependence of e is
left out here: with it, the problem is not a knapsack. The greedy's handling of it is
checked separately against a brute force (tests/v2/test_vmsim_bam.py).

Writes results/v2/bam_exact_check.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmsim import engine, scenarios, worlds  # noqa: E402
from vmsim.config import SimConfig  # noqa: E402
from vmsim.policies.bam import BAM  # noqa: E402
from vmsim.policies.base import Policy  # noqa: E402

MAX_N = 200


def greedy(b: np.ndarray, w: np.ndarray, cap: float) -> float:
    order = np.argsort(-(b / w), kind="stable")
    left, val = cap, 0.0
    for i in order:
        if b[i] <= 0:
            break
        if w[i] <= left:
            left -= w[i]
            val += b[i]
    return val


def exact(b: np.ndarray, w: np.ndarray, cap: float) -> float:
    pos = b > 0
    if not pos.any():
        return 0.0
    bb, ww = b[pos], w[pos]
    res = milp(
        c=-bb,
        constraints=LinearConstraint(ww[None, :], -np.inf, cap),
        integrality=np.ones(len(bb)),
        bounds=Bounds(0, 1),
        options={"mip_rel_gap": 1e-9},
    )
    if not res.success:
        raise RuntimeError(res.message)
    return float(-res.fun)


class Snapshot(Policy):
    """Records (b, w) of BAM's candidates on chosen days; migrates nothing."""

    name = "snapshot"

    def __init__(self, days):
        self.days, self.bam, self.out = set(days), BAM(), []

    def decide(self, obs, budget_gb):
        if obs.day in self.days:
            b = self.bam.benefit(obs)
            m = b > 0
            self.out.append((b[m], obs.vm_mem_gb[m], budget_gb, obs.host_free_gb.sum()))
        return np.zeros(0, dtype=np.int64)


def main() -> None:
    rng = np.random.default_rng(15)
    rows = []
    for cell in ("A3", "C"):
        cfg = scenarios.regime(SimConfig(n_hosts=1_000, horizon_days=150, name="x"), cell)
        for seed in (101, 102, 103):
            snap = Snapshot(range(40, 161, 20))
            engine.run(engine.prepare(worlds.generate(cfg, seed), cfg), snap, budget_frac=0.01)
            for b, w, _budget, _free in snap.out:
                if len(b) == 0:
                    continue
                k = rng.choice(len(b), min(MAX_N, len(b)), replace=False)
                b, w = b[k], w[k]
                for share in (0.1, 0.3, 0.6):  # how tight the budget is for this instance
                    cap = share * w.sum()
                    opt = exact(b, w, cap)
                    g = greedy(b, w, cap)
                    rows.append(("sim-" + cell, len(b), share, (opt - g) / opt if opt else 0.0))
    for _ in range(300):
        n = int(rng.integers(20, MAX_N + 1))
        b = rng.lognormal(0, 1.5, n)
        w = rng.lognormal(1.5, 0.8, n)
        share = float(rng.uniform(0.1, 0.5))
        cap = share * w.sum()
        opt = exact(b, w, cap)
        rows.append(("synth", n, share, (opt - greedy(b, w, cap)) / opt))

    out = {}
    for src in sorted({r[0] for r in rows}):
        gaps = np.array([r[3] for r in rows if r[0] == src])
        out[src] = {
            "instances": len(gaps),
            "mean_n": round(float(np.mean([r[1] for r in rows if r[0] == src])), 1),
            "gap_mean": float(gaps.mean()),
            "gap_median": float(np.median(gaps)),
            "gap_p95": float(np.quantile(gaps, 0.95)),
            "gap_max": float(gaps.max()),
            "share_exact": float((gaps < 1e-9).mean()),
        }
        print(src, out[src], flush=True)
    path = ROOT / "results" / "v2" / "bam_exact_check.json"
    path.write_text(json.dumps(out, indent=2))
    print("wrote", path)


if __name__ == "__main__":
    main()
