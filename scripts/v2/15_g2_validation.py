"""Week 13, gate G2: the numbers behind docs/v2/G2_simulator_validation.md (Table 4).

1. Analytic: constant hazard, one static VM per host, 20,000 hosts x 30 days (G2 #1)
     never migrate          interruptions vs N p_T
     move all at day 0      interruptions vs N p_T (memoryless: migration is pure cost)
2. Self-calibration across repairs: failures in (d, d+30] of hosts up at d vs the sum of the
   renewal oracle's p_H, 1,000 hosts, days 60/150/240, per decile of p (G2 #2)
3. v1 regression through vmsim's components (G2 #3)
4. Invariants and determinism: the hypothesis suite in tests/v2 (G2 #4; reported by pytest)
5. Run time: 5,000 hosts x 365 days, one core, each reference policy (G2 #5)

Writes results/v2/g2_validation.json.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "v2"))
from sim_helpers import MoveOnDay, constant_world  # noqa: E402

from vmsim import engine, v1_regression, worlds  # noqa: E402
from vmsim.config import SimConfig  # noqa: E402
from vmsim.policies import reference as R  # noqa: E402


def z(obs, n, p):
    return float((obs - n * p) / np.sqrt(n * p * (1 - p)))


def analytic() -> dict:
    n, h, T = 20_000, 0.01, 30
    p = 1 - (1 - h) ** T
    out = {"hosts": n, "daily_hazard": h, "days": T, "p_T": p, "expected": n * p}
    for name, pol in (("never", R.Never()), ("move_all_day0", MoveOnDay(0))):
        zs = []
        for seed in range(1, 6):
            s = engine.run(constant_world(n, h, T, seed=seed), pol)
            zs.append(z(s["interrupted_vms"], n, p))
        out[name] = {"z_by_seed": [round(v, 2) for v in zs], "max_abs_z": max(map(abs, zs))}
    return out


def self_calibration() -> dict:
    cfg = SimConfig(n_hosts=1_000, horizon_days=330, warmup_days=30)
    rows = []
    for seed in (11, 12, 13):
        prep = engine.prepare(worlds.generate(cfg, seed), cfg)
        pred = engine.make_predictor(prep)
        for d in (60, 150, 240):
            life_start = np.full(cfg.n_hosts, -1)
            up = np.ones(cfg.n_hosts, dtype=bool)
            for r in prep.sched:
                if r["t_fail"] < d:
                    life_start[r["host"]] = int(np.ceil(r["t_repair"]))
                    up[r["host"]] = np.ceil(r["t_repair"]) <= d
            p = pred.score(d, life_start).p_h
            nxt = np.array(
                [
                    f[np.searchsorted(f, d)] if np.searchsorted(f, d) < len(f) else np.inf
                    for f in prep.host_fails
                ]
            )
            rows.append(np.c_[p[up], ((nxt < d + 30) & up)[up]])
    a = np.concatenate(rows)
    p, y = a[:, 0], a[:, 1]
    dec = np.digitize(p, np.quantile(p, np.linspace(0.1, 0.9, 9)))
    deciles = []
    for k in range(10):
        m = dec == k
        e, v = p[m].sum(), (p[m] * (1 - p[m])).sum()
        deciles.append(
            {
                "decile": k + 1,
                "observed": int(y[m].sum()),
                "expected": round(float(e), 1),
                "z": round(float((y[m].sum() - e) / np.sqrt(v)), 2),
            }
        )
    e, v = p.sum(), (p * (1 - p)).sum()
    return {
        "host_windows": int(len(p)),
        "observed": int(y.sum()),
        "expected": round(float(e), 1),
        "z": round(float((y.sum() - e) / np.sqrt(v)), 2),
        "deciles": deciles,
        "max_abs_decile_z": max(abs(r["z"]) for r in deciles),
    }


def run_time() -> dict:
    cfg = SimConfig(n_hosts=5_000, horizon_days=365, warmup_days=30)
    prep = engine.prepare(worlds.generate(cfg, 201), cfg)
    out = {"hosts": 5_000, "days": 395, "target_s": 10.0, "machine": platform.platform()}
    for pol in (R.Never(), R.Threshold(), R.V1Rule(), R.Oracle(), R.RandomPick()):
        t = time.perf_counter()
        s = engine.run(prep, pol)
        out[pol.name] = {"wall_s": round(time.perf_counter() - t, 2), "migrations": s["migrations"]}
    out["max_s"] = max(v["wall_s"] for k, v in out.items() if k.startswith("P"))
    return out


def main() -> None:
    res = {}
    for name, fn in (
        ("analytic", analytic),
        ("self_calibration", self_calibration),
        ("v1_regression", v1_regression.run),
        ("run_time", run_time),
    ):
        t = time.time()
        res[name] = fn()
        print(f"{name}: {time.time() - t:.0f}s", flush=True)
    out = ROOT / "results" / "v2" / "g2_validation.json"
    out.write_text(json.dumps(res, indent=2, default=float))
    print(json.dumps({k: res[k] for k in ("analytic", "run_time")}, indent=1, default=float))
    print(
        "self-calibration z",
        res["self_calibration"]["z"],
        "max decile |z|",
        res["self_calibration"]["max_abs_decile_z"],
    )


if __name__ == "__main__":
    main()
