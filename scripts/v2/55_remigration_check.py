"""Dev-seed test of ADR-013's proposed cause: does BAM collapse through moving the same VMs again?

P4-once is BAM that may move a VM only once. If re-migration is the cause, P4-once recovers where
P4 collapses; if not, it stays negative. Dev seeds 101-105 only; exploratory, no verdict. Also
checks that the merged engine reproduces rows of the ADR-013 run.

  .venv/bin/python scripts/v2/55_remigration_check.py --workers 8
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmsim import engine, scenarios, worlds  # noqa: E402
from vmsim.policies.bam import BAM  # noqa: E402
from vmsim.policies.selective import BAMNet, SelectiveAvoid  # noqa: E402

_spec = importlib.util.spec_from_file_location("rm", ROOT / "scripts/v2/24_run_matrix.py")
RM = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RM)
M = yaml.safe_load((ROOT / "configs/v2/matrix.yaml").read_text())
TIERS = {"level": (1.0, 2.0, 10 / 3)}


class Counting:
    """Counts how often each VM is planned for a move; `once` drops VMs already moved."""

    def __init__(self, cls, once=False, **kw):
        self.p, self.once, self.moves = cls(**kw), once, {}
        self.name = self.p.name

    def __getattr__(self, k):
        return getattr(self.p, k)

    def decide(self, obs, budget_gb):
        plan = np.asarray(self.p.decide(obs, budget_gb), dtype=np.int64)
        if self.once:
            plan = plan[[v not in self.moves for v in plan.tolist()]] if len(plan) else plan
        for v in plan.tolist():
            self.moves[v] = self.moves.get(v, 0) + 1
        return plan


def prepared(regime, setting, seed):
    cell = f"{regime}@{setting}" if setting.startswith("G0") else regime
    cfg = scenarios.regime(RM.base_config(M), cell)
    if setting in TIERS:
        cfg = replace(cfg, cost=replace(cfg.cost, tier_weights=TIERS[setting]))
    return engine.prepare(worlds.generate(cfg, seed), cfg)


def one(job):
    regime, setting, seed = job
    prep = prepared(regime, setting, seed)
    p0 = float(
        engine.run(prep, RM.make_policy("P0", M, None), predictor=None, budget_frac=0.0)[
            "cost_total"
        ]
    )
    rows = []
    for pid, mk in (
        ("P4", lambda: Counting(BAM)),
        ("P4-net", lambda: Counting(BAMNet)),
        ("P4-once", lambda: Counting(BAM, once=True)),
    ):
        pol = mk()
        s = engine.run(prep, pol, predictor=None, budget_frac=0.02)
        n = np.array(list(pol.moves.values()) or [0])
        rows.append(
            {
                "regime": regime,
                "setting": setting,
                "seed": seed,
                "policy": pid,
                "saving": 100 * (1 - float(s["cost_total"]) / p0),
                "migrations": int(s["migrations"]),
                "planned": int(n.sum()),
                "vms_moved": int((n > 0).sum()),
                "max_moves": int(n.max()),
            }
        )
    return rows


def regression():
    out = []
    for reg, pid, pol in (
        ("B1", "P0+selective", SelectiveAvoid((0.02, 0.05, 0.10))),
        ("B2", "P4-net", BAMNet()),
    ):
        s = engine.run(prepared(reg, "default", 4001), pol, predictor=None, budget_frac=0.02)
        d = pd.read_parquet(ROOT / f"results/explore/selective_net/{reg}_4001.parquet")
        want = d[(d.setting == "default") & (d.sigma == 0) & (d.policy == pid)].total_cost.iloc[0]
        out.append(
            {
                "cell": f"{reg} {pid} 4001",
                "repo_engine": float(s["cost_total"]),
                "scratch_engine": float(want),
            }
        )
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    jobs = [
        (r, st, s)
        for r in ("B1", "B2")
        for st in ("default", "level", "G0-low")
        for s in range(101, 106)
    ]
    with ProcessPoolExecutor(a.workers) as ex:
        rows = [x for r in ex.map(one, jobs) for x in r]
    d = pd.DataFrame(rows)
    t = (
        d.groupby(["regime", "setting", "policy"])
        .mean(numeric_only=True)
        .drop(columns="seed")
        .round(2)
    )
    print(t.to_string())
    reg = regression()
    print(reg)
    (ROOT / "results/summary/remigration_check.json").write_text(
        json.dumps(
            {"note": "dev seeds 101-105; exploratory", "rows": rows, "engine_regression": reg},
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
