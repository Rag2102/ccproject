"""Week 20 runner: ablations, robustness grid, Morris screening, failure analysis (exploratory).

Config: configs/v2/w20.yaml. Scale, budgets and record format as the frozen matrix
(scripts/v2/24_run_matrix.py, whose helpers this reuses). Every phase is resumable (finished units
are skipped) and sharded with --shard i/N.
  ablate    BAM variants on A1, A3, A5, B1 at 1% and 2%, eval seeds -> W20/ablation/...
  rtune     P2 retuned per robustness setting and regime on dev seeds (owner, 5 Oct 2026)
  robust    all policies under each robustness setting (A3, B1 at 2%) and the F7 grid
  morris    one unit per trajectory point: fast P2 tune (2 dev seeds, 8 steps), then P2 and P4 on
            eval seeds 1-3; Delta = (C_P2 - C_P4) / C_P2
  failure   P2 and P4 with full outcomes written (A3, B1; 0.5, 2, 5%; seeds 1-5)
  collect   Parquet per phase under results/raw/W20/
"""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("rm", ROOT / "scripts/v2/24_run_matrix.py")
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)
from vmsim import engine, morris, scenarios, worlds  # noqa: E402
from vmsim.policies import reference as R  # noqa: E402
from vmsim.policies.bam import BAM, uniform_constants  # noqa: E402
from vmsim.policies.tune import tune_p2  # noqa: E402
from vmsim.predictor import Miscalibrated, Noisy, RenewalOracle  # noqa: E402

CFG = ROOT / "configs" / "v2" / "w20.yaml"
OUT = ROOT / "results" / "raw" / "W20"
log = rm.log


def load() -> tuple[dict, dict]:
    return rm.load_matrix(), yaml.safe_load(CFG.read_text())


def seeds_of(pair) -> list[int]:
    return list(range(pair[0], pair[1] + 1))


# --------------------------------------------------------------------------- settings
def apply(cfg, setting: dict):
    """Config with the setting's overrides; returns (cfg, predictor spec)."""
    pred = {}
    for k, v in setting.items():
        if k == "predictor":
            pred = dict(v)
            continue
        v = tuple(v) if isinstance(v, list) else v
        if "." in k:
            sec, f = k.split(".")
            cfg = replace(cfg, **{sec: replace(getattr(cfg, sec), **{f: v})})
        else:
            cfg = replace(cfg, **{k: v})
    return cfg, pred


def predictor_for(prep, pred: dict):
    """Oracle with noise and/or miscalibration (both may be set, as in the Morris screen)."""
    if not pred or (pred.get("sigma", 0) == 0 and pred.get("gamma", 1) == 1):
        return None
    o = RenewalOracle(prep.world.hazard, prep.renewed, prep.cfg.risk_h_days)
    if pred.get("sigma", 0):
        o = Noisy(o, float(pred["sigma"]), prep.streams)
    if pred.get("gamma", 1) != 1:
        o = Miscalibrated(o, float(pred["gamma"]))
    return o


def robustness_settings(w: dict) -> dict[str, tuple[list[str], dict, list[str]]]:
    """name -> (regimes, setting, policies), the F7 grid included."""
    r = w["robustness"]
    out = {n: (r["regimes"], s, r["policies"]) for n, s in r["settings"].items()}
    f7 = r["f7"]
    for bw, g in itertools.product(f7["bw"], f7["gamma"]):
        out[f"f7_bw{bw}_g{g}"] = (
            [f7["regime"]],
            {"migration.true_bw_factor": bw, "predictor": {"gamma": g}},
            f7["policies"],
        )
    return out


# --------------------------------------------------------------------------- policies
def bam_variant(pid: str, opts: dict) -> BAM:
    c_mean, m_mean = uniform_constants()
    kw = dict(opts)
    if kw.get("c_uniform") == "mean":
        kw["c_uniform"] = c_mean
    if kw.get("m_uniform") == "mean":
        kw["m_uniform"] = m_mean
    return BAM(name=pid, **kw)


def write_record(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, indent=1))
    os.replace(tmp, path)


def run_one(m, regime, pct, pid, seed, world, prep, pol, pred, card_c, extra, gsha, lock):
    t = time.time()
    s = engine.run(prep, pol, predictor=pred, budget_frac=pct / 100)
    meta = {"_git": gsha, "_lock": lock, **extra}
    return rm.record(
        m, regime, pct, pid, seed, "eval", world, s, card_c, meta, time.time() - t, pol
    )


# --------------------------------------------------------------------------- phases
def phase_ablate(m, w, shard):
    a = w["ablation"]
    units = [(r, s) for r in a["regimes"] for s in seeds_of(w["seeds"])]
    gsha, lock = rm.git_sha(), rm.sha256_file(ROOT / "uv.lock")
    for regime, seed in rm.shard_of(units, shard):
        todo = [
            (pid, pct, OUT / "ablation" / regime / f"b{pct:g}" / pid / f"s{seed:04d}.json")
            for pid in a["variants"]
            for pct in a["budgets_pct"]
        ]
        todo = [t for t in todo if not t[2].exists()]
        if not todo:
            continue
        cfg = scenarios.regime(rm.base_config(m), regime)
        world = worlds.generate(cfg, seed)
        prep = engine.prepare(world, cfg)
        cc = rm.card(m, regime)
        for pid, pct, path in todo:
            pol = bam_variant(pid, a["variants"][pid])
            rec = run_one(m, regime, pct, pid, seed, world, prep, pol, None, cc,
                          {"variant": a["variants"][pid]}, gsha, lock)  # fmt: skip
            write_record(path, rec)
        log(f"ablate {regime} seed {seed}: {len(todo)} runs")


def rtune_path(name: str, regime: str) -> Path:
    return OUT / "robust" / "tuning" / f"{name}_{regime}.json"


def phase_rtune(m, w, shard):
    pct = w["robustness"]["budget_pct"]
    a, b = m["seeds"]["dev"]
    units = [
        (n, r)
        for n, (regs, _, pols) in robustness_settings(w).items()
        for r in regs
        if "P2" in pols
    ]
    for name, regime in rm.shard_of(units, shard):
        path = rtune_path(name, regime)
        if path.exists():
            continue
        t = time.time()
        _, setting, _ = robustness_settings(w)[name]
        cfg, pred = apply(scenarios.regime(rm.base_config(m), regime), setting)
        preps = [engine.prepare(worlds.generate(cfg, s), cfg) for s in range(a, b + 1)]
        res = tune_p2(
            preps, pct / 100, criterion="budget", predictor=lambda p, pr=pred: predictor_for(p, pr)
        )
        res.update({"setting": name, "regime": regime, "budget_pct": pct})
        write_record(path, res)
        log(f"rtune {name} {regime}: tau {res['tau']:.3e} {res['order']} ({time.time() - t:.0f}s)")


def phase_robust(m, w, shard):
    pct = w["robustness"]["budget_pct"]
    sets = robustness_settings(w)
    units = [
        (n, r, s) for n, (regs, _, _) in sets.items() for r in regs for s in seeds_of(w["seeds"])
    ]
    gsha, lock = rm.git_sha(), rm.sha256_file(ROOT / "uv.lock")
    for name, regime, seed in rm.shard_of(units, shard):
        regs, setting, pols = sets[name]
        todo = []
        for pid in pols:
            b = 0 if pid == "P0" else pct
            path = OUT / "robust" / name / regime / f"b{b:g}" / pid / f"s{seed:04d}.json"
            if not path.exists():
                todo.append((pid, b, path))
        if not todo:
            continue
        cfg, pred = apply(scenarios.regime(rm.base_config(m), regime), setting)
        world = worlds.generate(cfg, seed)
        prep = engine.prepare(world, cfg)
        cc = rm.card(m, regime)
        cc["predictor"]["kind"] = "oracle" if not pred else json.dumps(pred, sort_keys=True)
        tune = json.loads(rtune_path(name, regime).read_text()) if "P2" in pols else None
        for pid, b, path in todo:
            pol = rm.make_policy(pid, m, tune)
            extra = {"setting": name}
            if tune and pid in ("P2", "P6"):
                extra.update({"tau": tune["tau"], "order": tune["order"]})
            pr = predictor_for(prep, pred)
            rec = run_one(m, regime, b, pid, seed, world, prep, pol, pr, cc, extra, gsha, lock)
            write_record(path, rec)
        log(f"robust {name} {regime} seed {seed}: {len(todo)} runs")


def morris_design(w):
    mo = w["morris"]
    names = list(mo["factors"])
    traj = morris.trajectories(len(names), mo["r"], mo["levels"], mo["seed"])
    return names, traj


def factor_values(names, x, spec) -> dict:
    out = {}
    for n, u in zip(names, x, strict=True):
        lo, hi, kind = spec[n]
        if kind == "log":
            out[n] = float(morris.scale(np.array(u), lo, hi, log=True))
        elif kind == "int":
            out[n] = int(round(lo + u * (hi - lo)))
        else:
            out[n] = float(morris.scale(np.array(u), lo, hi))
    return out


def phase_morris(m, w, shard):
    mo = w["morris"]
    names, traj = morris_design(w)
    units = [(t, j) for t in range(traj.shape[0]) for j in range(traj.shape[1])]
    main_tune = rm.tune_path(ROOT / "results" / "raw", mo["regime"], 2)
    order = json.loads(main_tune.read_text())["order"] if main_tune.exists() else "random"
    dev = list(range(mo["p2_tuning"]["dev_seeds"][0], mo["p2_tuning"]["dev_seeds"][1] + 1))
    for t, j in rm.shard_of(units, shard):
        path = OUT / "morris" / f"pt_{t:02d}_{j:02d}.json"
        if path.exists():
            continue
        t0 = time.time()
        v = factor_values(names, traj[t, j], mo["factors"])
        setting = {
            "migration.true_bw_factor": v["true_bw_factor"],
            "migration.true_dirty_factor": v["true_dirty_factor"],
            "migration.max_concurrent": v["max_concurrent"],
            "cost.d_fail_min": v["d_fail_min"],
            "failure.repair_median_days": v["repair_median_days"],
            "failure.non_disk_multiplier": v["non_disk_multiplier"],
            "placement.init_fill": v["init_fill"],
            "predictor": {"gamma": v["gamma"], "sigma": v["sigma"]},
        }
        cfg, pred = apply(scenarios.regime(rm.base_config(m), mo["regime"]), setting)
        b = v["budget_pct"] / 100
        preps = [engine.prepare(worlds.generate(cfg, s), cfg) for s in dev]
        tune = tune_p2(
            preps,
            b,
            criterion="budget",
            orders=(order,),
            steps=mo["p2_tuning"]["steps"],
            predictor=lambda p, pr=pred: predictor_for(p, pr),
        )
        deltas = []
        for s in seeds_of(mo["seeds"]):
            prep = engine.prepare(worlds.generate(cfg, s), cfg)
            p2 = R.Threshold(tune["tau"], tune["order"], "P2")
            c2 = engine.run(prep, p2, predictor=predictor_for(prep, pred), budget_frac=b)
            c2 = c2["cost_total"]
            c4 = engine.run(prep, BAM(), predictor=predictor_for(prep, pred), budget_frac=b)[
                "cost_total"
            ]
            deltas.append((c2 - c4) / c2)
        rec = {"t": t, "j": j, "x": traj[t, j].tolist(), "values": v, "tau": tune["tau"]}
        rec.update({"deltas": deltas, "delta_mean": float(np.mean(deltas))})
        write_record(path, rec)
        log(f"morris point {t}/{j}: delta {np.mean(deltas):+.4f} ({time.time() - t0:.0f}s)")


def phase_failure(m, w, shard):
    fa = w["failure_analysis"]
    units = [(r, s) for r in fa["regimes"] for s in seeds_of(fa["seeds"])]
    for regime, seed in rm.shard_of(units, shard):
        todo = [
            (pid, pct, OUT / "failure" / regime / f"b{pct:g}" / pid / f"s{seed:04d}")
            for pid in fa["policies"]
            for pct in fa["budgets_pct"]
        ]
        todo = [t for t in todo if not (t[2] / "summary.json").exists()]
        if not todo:
            continue
        cfg = scenarios.regime(rm.base_config(m), regime)
        prep = engine.prepare(worlds.generate(cfg, seed), cfg)
        for pid, pct, d in todo:
            tune = (
                json.loads(rm.tune_path(ROOT / "results" / "raw", regime, pct).read_text())
                if pid == "P2"
                else None
            )
            engine.run(prep, rm.make_policy(pid, m, tune), budget_frac=pct / 100, out_dir=d)
        log(f"failure {regime} seed {seed}: {len(todo)} runs")


def phase_collect():
    for phase in ("ablation", "robust"):
        files = [f for f in (OUT / phase).rglob("s*.json")]
        if not files:
            continue
        rows = []
        for f in files:
            rec = json.loads(f.read_text())
            row = rm.flatten(rec)
            pp = rec["policy"].get("params", {})
            row["setting"] = pp.get("setting", "base")
            rows.append(row)
        pd.DataFrame(rows).to_parquet(OUT / f"{phase}.parquet", index=False)
        log(f"{phase}: {len(rows)} runs collected")
    pts = sorted((OUT / "morris").glob("pt_*.json"))
    if pts:
        rows = []
        for f in pts:
            d = json.loads(f.read_text())
            rows.append({"t": d["t"], "j": d["j"], "delta_mean": d["delta_mean"], "tau": d["tau"],
                         **{f"x_{k}": v for k, v in d["values"].items()}})  # fmt: skip
        pd.DataFrame(rows).to_parquet(OUT / "morris.parquet", index=False)
        log(f"morris: {len(rows)} points collected")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--phase",
        required=True,
        choices=["ablate", "rtune", "robust", "morris", "failure", "collect"],
    )
    ap.add_argument("--shard")
    a = ap.parse_args()
    m, w = load()
    {
        "ablate": lambda: phase_ablate(m, w, a.shard),
        "rtune": lambda: phase_rtune(m, w, a.shard),
        "robust": lambda: phase_robust(m, w, a.shard),
        "morris": lambda: phase_morris(m, w, a.shard),
        "failure": lambda: phase_failure(m, w, a.shard),
        "collect": phase_collect,
    }[a.phase]()


if __name__ == "__main__":
    main()
