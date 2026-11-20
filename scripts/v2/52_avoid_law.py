"""ADR-012: test the concentration law for avoidance on fresh seeds (B1, B2, seeds 3001-3050).

Primary: P0+avoid over q x sigma, against phi R(q, sigma), verdict by the ADR's rule. Secondary:
prediction quality needed, rejected arrivals, the shuffled control, daily noise. Outside the
confirmatory family and G3.

  .venv/bin/python scripts/v2/52_avoid_law.py --derive   # R(q, sigma) from dev seeds 101-110
  .venv/bin/python scripts/v2/52_avoid_law.py            # run what is missing, then summarise
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmsim import engine, scenarios, worlds  # noqa: E402
from vmsim.policies.variants import AvoidTop  # noqa: E402
from vmsim.predictor import Scores, _expit, _logit  # noqa: E402

_spec = importlib.util.spec_from_file_location("rm", ROOT / "scripts/v2/24_run_matrix.py")
RM = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RM)

M = yaml.safe_load((ROOT / "configs/v2/matrix.yaml").read_text())
OUT = ROOT / "results" / "explore" / "avoid_law"
RFILE = ROOT / "results" / "summary" / "avoid_law_R.json"
ADR = ROOT / "docs/v2/DECISIONS/ADR-012-avoidance-concentration-law.md"
SEEDS = range(3001, 3051)
QS = [0.005, 0.01, 0.02, 0.05, 0.10]
SIGMAS = [0.0, 0.5, 1.0, 2.0]
QUALITY = [0.1, 0.25, 0.5, 1.0]
PHI = {"B1": 0.94, "B2": 0.75}


class Persistent:
    """Oracle with Gaussian logit noise, one draw per host per `block` days; `correct` shifts the
    log-odds by -sigma^2 / 2 so that noise alone does not inflate the mean of p."""

    def __init__(self, oracle, sigma, streams, block=30, correct=False):
        self.o, self.sigma, self.streams, self.block = oracle, sigma, streams, block
        self.shift = -(sigma**2) / 2 if correct else 0.0

    def score(self, day, life_start=None):
        s = self.o.score(day, life_start)
        z = self.streams.gen("predictor", 9, day // self.block).normal(size=len(s.p_h))
        p = _expit(_logit(s.p_interval) + (self.sigma * z + self.shift)[:, None])
        return Scores(p_h=p[:, 0], e_ttf=s.e_ttf, p_interval=p)


def derive() -> None:
    rng = np.random.default_rng(20261101)
    cfg = scenarios.regime(RM.base_config(M), "B2")
    acc = {(q, s): [] for q in QS for s in SIGMAS}
    for seed in range(101, 111):
        prep = engine.prepare(worlds.generate(cfg, seed), cfg)
        pred = engine.make_predictor(prep)
        for day in range(cfg.warmup_days, cfg.warmup_days + cfg.horizon_days, 15):
            p = np.asarray(pred.score(day).p_h, float)
            p = p[(p > 0) & (p < 1)]
            lg = np.log(p / (1 - p))
            for sg in SIGMAS:
                for _ in range(1 if sg == 0 else 5):
                    o = np.argsort(-(lg + sg * rng.normal(size=len(p))))
                    for q in QS:
                        k = max(1, round(q * len(p)))
                        acc[(q, sg)].append(p[o[:k]].sum() / p.sum())
    r = {f"{q}|{s}": (float(np.mean(v)) - q) / (1 - q) for (q, s), v in acc.items()}
    RFILE.write_text(json.dumps(r, indent=1))
    print(json.dumps(r, indent=1))


def row(prep, regime, seed, pid, q, sigma, kind, pol, pred, budget=0.02) -> dict:
    s = engine.run(prep, pol, predictor=pred, budget_frac=budget)
    return {"regime": regime, "seed": seed, "policy": pid, "q": q, "sigma": sigma, "kind": kind,
            "total_cost": float(s["cost_total"]), "migrations": int(s["migrations"]),
            "rejected_arrivals": int(s["rejected_arrivals"])}  # fmt: skip


def one(job: tuple[str, int]) -> list[dict]:
    regime, seed = job
    cfg = scenarios.regime(RM.base_config(M), "B1" if regime == "B1-noblend" else regime)
    if regime == "B1-noblend":
        cfg = replace(cfg, placement=replace(cfg.placement, arrival_blend=None))
    prep = engine.prepare(worlds.generate(cfg, seed), cfg)
    orc = engine.make_predictor(prep)
    p0 = RM.make_policy("P0", M, None)
    rows = [row(prep, regime, seed, "P0", 0.0, 0.0, "base", p0, None, budget=0.0)]
    shuf = engine.make_predictor(prep, "noise")
    rows.append(row(prep, regime, seed, "P0+avoid", 0.02, 9.0, "shuffled", AvoidTop(0.02), shuf))
    if regime not in ("B1", "B2"):
        return rows
    for q in QS:
        for sg in SIGMAS:
            pred = None if sg == 0 else Persistent(orc, sg, prep.streams)
            rows.append(row(prep, regime, seed, "P0+avoid", q, sg, "law", AvoidTop(q), pred))
    daily = engine.make_predictor(prep, "noisy", sigma=1.0)
    rows.append(row(prep, regime, seed, "P0+avoid", 0.02, 1.0, "daily", AvoidTop(0.02), daily))
    for sg in QUALITY:
        for pid, correct in [("P0+avoid", False), ("P4", False), ("P5", False), ("P4-c", True)]:
            pred = Persistent(orc, sg, prep.streams, correct=correct)
            pol = AvoidTop(0.02) if pid == "P0+avoid" else RM.make_policy(pid[:2], M, None)
            rows.append(row(prep, regime, seed, pid, 0.02, sg, "quality", pol, pred))
    for pid in ("P4", "P5"):
        pol = RM.make_policy(pid, M, None)
        rows.append(row(prep, regime, seed, pid, 0.02, 0.0, "quality", pol, None))
    return rows


def bca(x: np.ndarray) -> list[float]:
    r = stats.bootstrap((x,), np.mean, n_resamples=10_000, method="BCa",
                        random_state=np.random.default_rng(20261101))  # fmt: skip
    return [float(r.confidence_interval.low), float(r.confidence_interval.high)]


def cross_zero(sig: list[float], val: list[float]) -> float | None:
    for a, b, x, y in zip(sig[:-1], sig[1:], val[:-1], val[1:], strict=True):
        if x > 0 >= y:
            return float(a + (b - a) * x / (x - y))
    return None


def summarise() -> None:
    d = pd.concat([pd.read_parquet(f) for f in sorted(OUT.glob("*.parquet"))], ignore_index=True)
    base = d[d.kind == "base"].set_index(["regime", "seed"]).total_cost
    d["saving"] = [1 - c / base[(r, s)] for r, s, c in zip(d.regime, d.seed, d.total_cost, strict=True)]
    R = json.loads(RFILE.read_text())
    cells, tests = [], {}
    for reg in ("B1", "B2"):
        a = d[(d.regime == reg) & (d.kind == "law")]
        rej0 = d[(d.regime == reg) & (d.kind == "base")].rejected_arrivals.mean()
        pred, obs = [], []
        for q in QS:
            for sg in SIGMAS:
                x = a[(a.q == q) & (a.sigma == sg)]
                v = x.saving.to_numpy()
                pr = PHI[reg] * R[f"{q}|{sg}"]
                anchor = q == 0.02 and sg == 0
                cells.append({"regime": reg, "q": q, "sigma": sg, "predicted": pr, "observed": float(v.mean()),
                              "ci_bca": bca(v), "rejected_arrivals": float(x.rejected_arrivals.mean()),
                              "rejected_p0": float(rej0), "anchor_on_other_seeds": anchor})  # fmt: skip
                if not anchor:
                    pred.append(pr)
                    obs.append(float(v.mean()))
        err = float(np.mean(np.abs(np.array(pred) - np.array(obs))))
        tests[reg] = {"n_cells": len(pred), "spearman": float(stats.spearmanr(pred, obs).statistic), "mae_points": err * 100}
    sp = all(t["spearman"] >= 0.9 for t in tests.values())
    mae = all(t["mae_points"] <= 2 for t in tests.values())
    verdict = "supported" if sp and mae else "direction only" if sp else "not supported"
    quality = {}
    for reg in ("B1", "B2"):
        quality[reg] = {}
        for pid in ("P0+avoid", "P4", "P4-c", "P5"):
            q = d[(d.regime == reg) & (d.kind == "quality") & (d.policy == pid)]
            sig, val, ci = [], [], []
            if pid == "P0+avoid":
                z = d[(d.regime == reg) & (d.kind == "law") & (d.q == 0.02) & (d.sigma == 0)]
            elif pid == "P4-c":
                z = d[(d.regime == reg) & (d.kind == "quality") & (d.policy == "P4") & (d.sigma == 0)]
            else:
                z = q[q.sigma == 0]
            for sg in [0.0, *QUALITY]:
                x = (z if sg == 0 else q[q.sigma == sg]).saving.to_numpy()
                sig.append(sg)
                val.append(float(x.mean()))
                ci.append(bca(x))
            quality[reg][pid] = {"sigma": sig, "saving": val, "ci_bca": ci, "break_even_sigma": cross_zero(sig, val)}
    shuffled = {}
    for reg in ("B1", "B2", "A1", "B1-noblend"):
        x = d[(d.regime == reg) & (d.kind == "shuffled")].saving.to_numpy()
        shuffled[reg] = {"saving": float(x.mean()), "ci_bca": bca(x)}
    dd = {}
    for reg in ("B1", "B2"):
        x = d[(d.regime == reg) & (d.kind == "daily")].saving.to_numpy()
        dd[reg] = {"saving": float(x.mean()), "ci_bca": bca(x)}
    out = ROOT / "results" / "summary" / "avoid_law.json"
    out.write_text(json.dumps({"rule": "ADR-012", "adr_sha256": hashlib.sha256(ADR.read_bytes()).hexdigest(),
                               "verdict": verdict, "tests": tests, "cells": cells, "quality": quality,
                               "shuffled": shuffled, "daily_sigma1_q2": dd}, indent=1))  # fmt: skip
    print(verdict, json.dumps(tests))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--derive", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    if a.derive:
        derive()
        return
    OUT.mkdir(parents=True, exist_ok=True)
    for reg in ("B1", "B2", "A1", "B1-noblend"):
        f = OUT / f"{reg}.parquet"
        if not f.exists():
            with ProcessPoolExecutor(a.workers) as ex:
                rows = [r for part in ex.map(one, [(reg, s) for s in SEEDS]) for r in part]
            pd.DataFrame(rows).to_parquet(f, index=False)
    summarise()


if __name__ == "__main__":
    main()
