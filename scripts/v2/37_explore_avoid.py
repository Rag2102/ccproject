"""ADR-010 (exploratory, post-freeze): placement-time avoidance on the evaluation seeds.

Runs P0+avoid (mark the riskiest 2% of hosts each day so they take no new VMs; never migrate) and
P4+avoid (BAM plus the same marks) on the frozen matrix's worlds: every regime of groups A-E,
eval seeds 1-30, budgets 1% and 2% (P0+avoid at 2% only: it uses no budget, but the engine takes
no mitigation action at all at a zero budget). Same scale, worlds and predictor pairing as
24_run_matrix.py (oracle; drift for D). Outside the confirmatory family and the G3 rule.

Writes results/explore/avoid/<regime>.parquet (one row per run; resumable per regime) and, when
the matching P0 runs exist in results/raw, results/summary/explore_avoid.json: the saving against
never migrating per (regime, budget, policy) with a 95% BCa interval, beside P4 and P5.

  .venv/bin/python scripts/v2/37_explore_avoid.py           # run what is missing, then summarise
  .venv/bin/python scripts/v2/37_explore_avoid.py --summary-only
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmsim import engine, scenarios, worlds  # noqa: E402
from vmsim.policies.variants import AvoidTop, BAMAvoid  # noqa: E402

_spec = importlib.util.spec_from_file_location("rm", ROOT / "scripts/v2/24_run_matrix.py")
RM = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RM)

M = yaml.safe_load((ROOT / "configs/v2/matrix.yaml").read_text())
RUNS = [("P0+avoid", 2.0), ("P4+avoid", 1.0), ("P4+avoid", 2.0)]
MAKE = {"P0+avoid": lambda: AvoidTop(0.02), "P4+avoid": lambda: BAMAvoid(0.02)}


def one(job: tuple[str, int]) -> list[dict]:
    regime, seed = job
    cfg = scenarios.regime(RM.base_config(M), regime)
    world = worlds.generate(cfg, seed)
    prep = engine.prepare(world, cfg)
    kind = M.get("predictor_by_regime", {}).get(regime, "oracle")
    rows = []
    for pid, pct in RUNS:
        pred = engine.make_predictor(prep, kind, gamma=0.7) if kind != "oracle" else None
        t = time.time()
        s = engine.run(prep, MAKE[pid](), predictor=pred, budget_frac=pct / 100,
                       predictor_label=kind)  # fmt: skip
        rows.append(
            {
                "regime": regime,
                "seed": seed,
                "policy": pid,
                "budget_pct": pct,
                "predictor": kind,
                "world_sha256": world.digest(),
                "total_cost": float(s["cost_total"]),
                "interruption_cost": float(
                    s["cost_interrupt_resident"] + s["cost_interrupt_transient"]
                ),
                "migration_cost": float(s["cost_migration"]),
                "migrations": int(s["migrations"]),
                "rejected_arrivals": int(s["rejected_arrivals"]),
                "git_sha": RM.git_sha(),
                "seconds": round(time.time() - t, 2),
            }
        )
    return rows


def bca(x: np.ndarray) -> list[float]:
    if len(x) < 3 or np.allclose(x, x[0]):
        return [float(x.mean())] * 2
    r = stats.bootstrap((x,), np.mean, n_resamples=10_000, method="BCa",
                        random_state=np.random.default_rng(20261004))  # fmt: skip
    return [float(r.confidence_interval.low), float(r.confidence_interval.high)]


def summarise(out_dir: Path) -> None:
    ex = [pd.read_parquet(f) for f in sorted(out_dir.glob("*.parquet"))]
    if not ex:
        print("no exploratory runs yet")
        return
    ex = pd.concat(ex, ignore_index=True)
    raw = [pd.read_parquet(f) for f in glob.glob(str(ROOT / "results/raw/[A-E]/*.parquet"))]
    if not raw:
        print("no P0 runs in results/raw yet; summary skipped")
        return
    raw = pd.concat(raw, ignore_index=True)
    raw = raw[raw.family == "eval"]
    p0 = raw[raw.policy == "P0"].set_index(["regime", "seed"]).total_cost
    ref = raw[raw.policy.isin(["P4", "P5"]) & raw.budget_pct.isin([1.0, 2.0])]
    cols = ["regime", "seed", "policy", "budget_pct", "total_cost", "migrations"]
    both = pd.concat([ex[cols], ref[cols]])
    cells = []
    for (reg, b, pol), g in both.groupby(["regime", "budget_pct", "policy"]):
        base = p0.reindex(list(zip(g.regime, g.seed, strict=True))).to_numpy()
        ok = np.isfinite(base) & (base > 0)
        if not ok.any():
            continue
        s = (base[ok] - g.total_cost.to_numpy()[ok]) / base[ok]
        cells.append(
            {
                "regime": reg,
                "budget_pct": float(b),
                "policy": pol,
                "n_seeds": int(ok.sum()),
                "saving_vs_p0_mean": float(s.mean()),
                "ci_bca": bca(s),
                "share_seeds_beating_p0": float((s > 0).mean()),
                "migrations_mean": float(g.migrations.to_numpy()[ok].mean()),
                "family": "exploratory",
            }
        )
    out = ROOT / "results" / "summary" / "explore_avoid.json"
    note = (
        "ADR-010, exploratory: saving = (C_P0 - C) / C_P0 per seed; eval seeds; "
        "P4 and P5 for reference"
    )
    out.write_text(json.dumps({"note": note, "cells": cells}, indent=1))
    print(f"{len(cells)} cells -> {out.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--regimes", nargs="+")
    ap.add_argument("--seeds", default="1-30")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default=str(ROOT / "results" / "explore" / "avoid"))
    ap.add_argument("--summary-only", action="store_true")
    a = ap.parse_args()
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not a.summary_only:
        regimes = a.regimes or [r for g in "ABCDE" for r in M["regimes"][g]]
        lo, hi = map(int, a.seeds.split("-"))
        for reg in regimes:
            f = out_dir / f"{reg}.parquet"
            if f.exists():
                print(f"{reg}: done, skipped", flush=True)
                continue
            t = time.time()
            with ProcessPoolExecutor(a.workers) as ex:
                jobs = [(reg, s) for s in range(lo, hi + 1)]
                rows = [r for part in ex.map(one, jobs) for r in part]
            pd.DataFrame(rows).to_parquet(f, index=False)
            print(f"{time.strftime('%H:%M:%S')} {reg}: {len(rows)} runs in {time.time() - t:.0f}s",
                  flush=True)  # fmt: skip
    summarise(out_dir)


if __name__ == "__main__":
    main()
