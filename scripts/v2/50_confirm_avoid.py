"""ADR-011: confirm the avoidance finding on fresh seeds (B1, B2, seeds 2001-2050, 2% budget).

Primary: P0+avoid against P0, P4 and P5 (6 comparisons, Holm), verdict by the ADR's rule. Secondary:
rejected arrivals, P4+avoid, and imperfect predictors. Outside the confirmatory family and G3.

  .venv/bin/python scripts/v2/50_confirm_avoid.py                # run what is missing, then summarise
  .venv/bin/python scripts/v2/50_confirm_avoid.py --check-seed 1   # compare with the frozen cells
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
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
OUT = ROOT / "results" / "explore" / "avoid_confirm"
REGIMES = ["B1", "B2"]
SEEDS = range(2001, 2051)
SIGMAS = [0.5, 1.0, 2.0]
MIN_DIFF = 0.01


def policy(pid: str):
    if pid == "P0+avoid":
        return AvoidTop(0.02)
    if pid == "P4+avoid":
        return BAMAvoid(0.02)
    return RM.make_policy(pid, M, None)


def row(prep, regime, seed, pid, pct, label, pred) -> dict:
    s = engine.run(prep, policy(pid), predictor=pred, budget_frac=pct / 100, predictor_label=label)
    return {
        "regime": regime,
        "seed": seed,
        "policy": pid,
        "budget_pct": pct,
        "predictor": label,
        "total_cost": float(s["cost_total"]),
        "migrations": int(s["migrations"]),
        "rejected_arrivals": int(s["rejected_arrivals"]),
    }


def one(job: tuple[str, int]) -> list[dict]:
    regime, seed = job
    cfg = scenarios.regime(RM.base_config(M), regime)
    prep = engine.prepare(worlds.generate(cfg, seed), cfg)
    rows = [row(prep, regime, seed, "P0", 0.0, "oracle", None)]
    for pid in ("P4", "P5", "P0+avoid", "P4+avoid"):
        rows.append(row(prep, regime, seed, pid, 2.0, "oracle", None))
    for pid in ("P0+avoid", "P4"):
        for sig in SIGMAS:
            pred = engine.make_predictor(prep, "noisy", sigma=sig)
            rows.append(row(prep, regime, seed, pid, 2.0, f"noisy_{sig:g}", pred))
        pred = engine.make_predictor(prep, "noise")
        rows.append(row(prep, regime, seed, pid, 2.0, "noise", pred))
    return rows


def bca(x: np.ndarray) -> list[float]:
    r = stats.bootstrap((x,), np.mean, n_resamples=10_000, method="BCa",
                        random_state=np.random.default_rng(20261101))  # fmt: skip
    return [float(r.confidence_interval.low), float(r.confidence_interval.high)]


def saving(d: pd.DataFrame, regime: str, pid: str, label: str = "oracle") -> pd.Series:
    r = d[d.regime == regime]
    base = r[r.policy == "P0"].set_index("seed").total_cost
    c = r[(r.policy == pid) & (r.predictor == label)].set_index("seed").total_cost
    return (base - c) / base


def holm(p: list[float]) -> list[float]:
    order, out, top = np.argsort(p), [0.0] * len(p), 0.0
    for i, k in enumerate(order):
        top = max(top, min(1.0, (len(p) - i) * p[k]))
        out[k] = float(top)
    return out


def summarise() -> None:
    d = pd.concat([pd.read_parquet(f) for f in sorted(OUT.glob("*.parquet"))], ignore_index=True)
    prim = []
    for reg in REGIMES:
        a = saving(d, reg, "P0+avoid")
        for other in ("P0", "P4", "P5"):
            diff = a if other == "P0" else a - saving(d, reg, other)
            x = diff.dropna().to_numpy()
            prim.append({"regime": reg, "against": other, "n": len(x), "diff_mean": float(x.mean()),
                         "ci_bca": bca(x), "wilcoxon_p": float(stats.wilcoxon(x).pvalue)})  # fmt: skip
    for c, h in zip(prim, holm([c["wilcoxon_p"] for c in prim]), strict=True):
        c["holm_p"] = h
        c["passed"] = bool(c["diff_mean"] >= MIN_DIFF and h < 0.05 and c["ci_bca"][0] > 0)
    against_p0 = all(c["passed"] for c in prim if c["against"] == "P0")
    others = sum(c["passed"] for c in prim if c["against"] != "P0")
    verdict = (
        "confirmed"
        if against_p0 and others == 4
        else "partly confirmed"
        if against_p0 and others >= 1
        else "not confirmed"
    )
    sec = []
    for reg in REGIMES:
        for pid, label in [("P4", "oracle"), ("P5", "oracle"), ("P0+avoid", "oracle"),
                           ("P4+avoid", "oracle")] + [
            (p, x) for p in ("P0+avoid", "P4") for x in [f"noisy_{s:g}" for s in SIGMAS] + ["noise"]
        ]:  # fmt: skip
            x = saving(d, reg, pid, label).dropna().to_numpy()
            r = d[(d.regime == reg) & (d.policy == pid) & (d.predictor == label)]
            sec.append({"regime": reg, "policy": pid, "predictor": label,
                        "saving_mean": float(x.mean()), "ci_bca": bca(x),
                        "migrations_mean": float(r.migrations.mean()),
                        "rejected_arrivals_mean": float(r.rejected_arrivals.mean())})  # fmt: skip
        base = d[(d.regime == reg) & (d.policy == "P0")]
        sec.append({"regime": reg, "policy": "P0", "predictor": "oracle", "saving_mean": 0.0,
                    "rejected_arrivals_mean": float(base.rejected_arrivals.mean())})  # fmt: skip
    out = ROOT / "results" / "summary" / "avoid_confirm.json"
    out.write_text(json.dumps({"rule": "ADR-011", "verdict": verdict, "primary": prim,
                               "secondary": sec}, indent=1))  # fmt: skip
    print(verdict)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check-seed", type=int)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    if a.check_seed:
        # same engine path as the frozen runner: these must equal the committed cells
        for reg in REGIMES:
            cfg = scenarios.regime(RM.base_config(M), reg)
            prep = engine.prepare(worlds.generate(cfg, a.check_seed), cfg)
            for pid, pct, name in [("P0", 0.0, "b0"), ("P4", 2.0, "b2"), ("P5", 2.0, "b2")]:
                got = row(prep, reg, a.check_seed, pid, pct, "oracle", None)["total_cost"]
                raw = pd.read_parquet(ROOT / f"results/raw/B/{reg}_{name}_{pid}.parquet")
                want = float(raw[raw.seed == a.check_seed].total_cost.iloc[0])
                print(reg, pid, got, want, "same" if abs(got - want) < 1e-6 else "DIFFERENT")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    for reg in REGIMES:
        f = OUT / f"{reg}.parquet"
        if not f.exists():
            with ProcessPoolExecutor(a.workers) as ex:
                rows = [r for part in ex.map(one, [(reg, s) for s in SEEDS]) for r in part]
            pd.DataFrame(rows).to_parquet(f, index=False)
    summarise()


if __name__ == "__main__":
    main()
