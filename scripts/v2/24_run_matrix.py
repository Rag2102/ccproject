"""Week 17, task 6: the sharded, resumable runner for the frozen matrix (configs/v2/matrix.yaml).

Phases (each resumable: finished units are skipped, so a crashed shard is simply restarted):
  cards    write one scenario card per regime (configs/v2/cards/<id>.yaml) and its SHA-256
  tune     P2's tau and within-host order per (regime, budget) on dev seeds, criterion "budget"
           (ADR-005) -> <root>/tuning/<regime>_b<pct>.json
  run      for each (regime, eval seed) in this shard: one world, then every policy and budget
           -> one vmmbench/1 record per run, <root>/<group>/<regime>/b<pct>/<policy>/s<seed>.json
           (P0 once per world, at budget 0)
  collect  one Parquet per cell (regime, budget, policy) when all its seeds are present, a
           manifest with SHA-256 per file, and a completeness report (no policy comparisons)

<root> is results/raw (or results/dryrun with --dry-run: 2 dev seeds and 4 bisection steps for
tuning; use --seeds 1-2). Shards: --shard i/N takes every N-th unit, so N processes cover the
matrix without overlap. Example: for i in 1..8: 24_run_matrix.py --phase run --groups A E
--seeds 1-30 --shard i/8.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmmbench.validate import check  # noqa: E402
from vmsim import accounting, engine, scenarios, worlds  # noqa: E402
from vmsim.config import SimConfig  # noqa: E402
from vmsim.policies import reference as R  # noqa: E402
from vmsim.policies.bam import BAM  # noqa: E402
from vmsim.policies.guard import SafeGuard  # noqa: E402
from vmsim.policies.narya import Narya  # noqa: E402
from vmsim.policies.tune import tune_p2  # noqa: E402

MATRIX = ROOT / "configs" / "v2" / "matrix.yaml"
CARDS = ROOT / "configs" / "v2" / "cards"


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def load_matrix() -> dict:
    return yaml.safe_load(MATRIX.read_text())


def seed_range(s: str) -> list[int]:
    a, _, b = s.partition("-")
    return list(range(int(a), int(b or a) + 1))


def shard_of(items: list, shard: str | None) -> list:
    if not shard:
        return items
    i, n = (int(x) for x in shard.split("/"))
    return items[i - 1 :: n]


def group_of(m: dict, regime: str) -> str:
    return next(g for g, rs in m["regimes"].items() if regime in rs)


def base_config(m: dict) -> SimConfig:
    s = m["scale"]
    return SimConfig(
        n_hosts=s["n_hosts"],
        horizon_days=s["horizon_days"],
        warmup_days=s["warmup_days"],
        risk_h_days=s["risk_h_days"],
        name="matrix",
    )


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git_sha() -> str:
    sha = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain", "--", "vmsim", "scripts/v2", "configs"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    return sha + ("+dirty" if dirty else "")


# --------------------------------------------------------------------------- cards
def card(m: dict, regime: str) -> dict:
    cfg = scenarios.regime(base_config(m), regime)
    pc, fc, mc = cfg.placement, cfg.failure, cfg.migration
    kind = {
        "random": "heterogeneity_only" if cfg.cost.kappa_sigma is not None else "random",
        "rho": "nonstationary" if pc.switch_day is not None else "latent_copula",
        "class": "class_conditional",
        "adversarial": "adversarial",
    }[pc.regime]
    if regime.startswith("B1"):
        kind = "rank_copula"
    return {
        "id": regime,
        "version": m["version"],
        "placement": {
            "kind": kind,
            "rho_latent": scenarios.latent_of(regime),
            "target_spearman": pc.rho,
            "arrival_blend": pc.arrival_blend,
            "kappa_sigma": cfg.cost.kappa_sigma,
            "calibrations": [regime.split("-")[1] if "-" in regime else "point"],
        },
        "hosts": {
            "n": cfg.n_hosts,
            "drives_per_host": fc.drives_per_host,
            "non_disk_hazard_x": fc.non_disk_multiplier,
        },
        "horizon_days": cfg.horizon_days,
        "warmup_days": cfg.warmup_days,
        "predictor": {"kind": m["predictor_by_regime"].get(regime, m["predictor"])},
        "migration": {
            "model": "precopy",
            "nic_gbps": mc.nic_gbps,
            "usable_frac": mc.usable_share,
            "max_concurrent": mc.max_concurrent,
        },
        "budget": {"resource": "gb", "pct_cluster_mem_per_day": m["budgets_pct"]},
        "seeds": {k: f"{a}-{b}" for k, (a, b) in m["seeds"].items()},
        "provenance": {
            "rho": "MEASURED" if regime.startswith("B") else "ASSUMED",
            "hazard": "DERIVED",
            "migration": "ASSUMED",
            "costs": "DERIVED",
        },
        "config_hash": accounting.config_hash(cfg.to_dict()),
    }


def card_sha(c: dict) -> str:
    return hashlib.sha256(json.dumps(c, sort_keys=True, default=str).encode()).hexdigest()


def phase_cards(m: dict) -> None:
    CARDS.mkdir(parents=True, exist_ok=True)
    for regs in m["regimes"].values():
        for r in regs:
            c = card(m, r)
            check({k: v for k, v in c.items() if k != "config_hash"}, "scenario_card")
            (CARDS / f"{r}.yaml").write_text(yaml.safe_dump(c, sort_keys=False))
            log(f"card {r}: {card_sha(c)[:12]}")


# --------------------------------------------------------------------------- tune
def tune_path(root: Path, regime: str, pct: float) -> Path:
    return root / "tuning" / f"{regime}_b{pct:g}.json"


def phase_tune(m: dict, root: Path, groups: list[str], shard: str | None, dry: bool) -> None:
    units = [(r, b) for g in groups for r in m["regimes"][g] for b in m["budgets_pct"]]
    a, b = m["seeds"]["dev"]
    dev = [101, 102] if dry else list(range(a, b + 1))
    for regime, pct in shard_of(units, shard):
        out = tune_path(root, regime, pct)
        if out.exists():
            continue
        t = time.time()
        cfg = scenarios.regime(base_config(m), regime)
        preps = [engine.prepare(worlds.generate(cfg, s), cfg) for s in dev]
        res = tune_p2(preps, pct / 100, criterion="budget", steps=4 if dry else 12)
        res.update({"regime": regime, "budget_pct": pct, "dev_seeds": dev})
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".tmp")
        tmp.write_text(json.dumps(res, indent=2, default=float))
        os.replace(tmp, out)
        dt = time.time() - t
        log(f"tuned {regime} @ {pct}%: tau {res['tau']:.3e} {res['order']} ({dt:.0f}s)")


# --------------------------------------------------------------------------- run
def make_policy(pid: str, m: dict, tune: dict | None):
    if pid in ("P0", "P1", "P3", "P7", "P8"):
        return R.by_name(pid)
    if pid == "P2":
        return R.Threshold(tune["tau"], tune["order"], "P2")
    if pid == "P4":
        return BAM()
    if pid == "P5":
        return Narya("faithful", name="P5")
    if pid == "P6":
        k = dict(m["p6"])
        k["slope_band"] = tuple(k["slope_band"])
        return SafeGuard(R.Threshold(tune["tau"], tune["order"], "P2"), BAM(), **k)
    raise ValueError(pid)


def record(m, regime, pct, pid, seed, family, world, s, card_c, meta, seconds, policy) -> dict:
    rec = {
        "schema": "vmmbench/1",
        "scenario": {
            "id": regime,
            "version": m["version"],
            "card_sha256": card_sha(card_c),
            "calibration": card_c["placement"]["calibrations"][0],
        },
        "world": {"seed": seed, "family": family, "world_sha256": world.digest()},
        "policy": {
            "id": pid,
            "version": "2.0.0",
            "predictor": card_c["predictor"]["kind"],
            "params": meta,
        },
        "budget": {
            "resource": "gb",
            "pct": float(pct),
            "utilisation": float(s["budget_utilisation"]),
            "overspend": bool(s["max_daily_overspend_gb"] > 1e-6),
        },
        "metrics": {
            "total_cost": float(s["cost_total"]),
            "interruption_cost": float(
                s["cost_interrupt_resident"] + s["cost_interrupt_transient"]
            ),
            "migration_cost": float(s["cost_migration"]),
            "missed_failures": int(s["interrupted_vms"] + s["interrupted_transient_vms"]),
            "unnecessary_migrations": int(s.get("migrations_unnecessary", 0)),
            "realised_failures": int(s["host_failures"]),
            "migrations": int(s["migrations"]),
            "rejected_arrivals": int(s["rejected_arrivals"]),
            "rho_tier_risk_horizon": None
            if not np.isfinite(s["rho_tier_risk_horizon"])
            else float(s["rho_tier_risk_horizon"]),
        },
        "run": {
            "git_sha": meta.pop("_git"),
            "config_hash": card_c["config_hash"],
            "lockfile_sha256": meta.pop("_lock"),
            "seconds": round(seconds, 3),
            "outcomes_sha256": s["outcomes_sha256"],
        },
    }
    if isinstance(policy, SafeGuard):
        rec["policy"]["params"]["mode_days"] = dict(policy.mode_days)
        rec["policy"]["params"]["switches"] = [(int(x["day"]), x["to"]) for x in policy.switches]
    check(rec, "vmmbench_result")
    return rec


def rec_path(root: Path, group: str, regime: str, pct: float, pid: str, seed: int) -> Path:
    return root / group / regime / f"b{pct:g}" / pid / f"s{seed:04d}.json"


def phase_run(m, root, groups, seeds, shard, family) -> None:
    units = [(r, s) for g in groups for r in m["regimes"][g] for s in seeds]
    gsha, lock = git_sha(), sha256_file(ROOT / "uv.lock")
    for regime, seed in shard_of(units, shard):
        group = group_of(m, regime)
        todo = []
        for pid in m["policies"]:
            for pct in [0] if pid == "P0" else m["budgets_pct"]:
                p = rec_path(root, group, regime, pct, pid, seed)
                if not p.exists():
                    todo.append((pid, pct, p))
        if not todo:
            continue
        t0 = time.time()
        cfg = scenarios.regime(base_config(m), regime)
        world = worlds.generate(cfg, seed)
        prep = engine.prepare(world, cfg)
        cc = card(m, regime)
        kind = cc["predictor"]["kind"]
        for pid, pct, p in todo:
            tune = None
            if pid in ("P2", "P6"):
                tune = json.loads(tune_path(root, regime, pct).read_text())
            pol = make_policy(pid, m, tune)
            pred = engine.make_predictor(prep, kind, gamma=0.7) if kind != "oracle" else None
            t = time.time()
            s = engine.run(prep, pol, predictor=pred, budget_frac=pct / 100, predictor_label=kind)
            meta = {"_git": gsha, "_lock": lock}
            if tune:
                meta.update({"tau": tune["tau"], "order": tune["order"]})
            dt = time.time() - t
            rec = record(m, regime, pct, pid, seed, family, world, s, cc, meta, dt, pol)
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(rec, indent=1))
            os.replace(tmp, p)
        log(f"{regime} seed {seed}: {len(todo)} runs in {time.time() - t0:.0f}s")


# --------------------------------------------------------------------------- collect
def flatten(rec: dict) -> dict:
    out = {
        "regime": rec["scenario"]["id"],
        "seed": rec["world"]["seed"],
        "family": rec["world"]["family"],
        "world_sha256": rec["world"]["world_sha256"],
        "policy": rec["policy"]["id"],
        "predictor": rec["policy"]["predictor"],
        "budget_pct": rec["budget"]["pct"],
        "utilisation": rec["budget"]["utilisation"],
        "overspend": rec["budget"]["overspend"],
        "git_sha": rec["run"]["git_sha"],
        "seconds": rec["run"]["seconds"],
        "outcomes_sha256": rec["run"]["outcomes_sha256"],
    }
    out.update(rec["metrics"])
    pp = rec["policy"].get("params", {})
    for k in ("tau", "order"):
        if k in pp:
            out[k] = pp[k]
    if "mode_days" in pp:
        out["p6_days_bam"] = pp["mode_days"].get("BAM", 0)
        out["p6_switches"] = len(pp["switches"])
    return out


def phase_collect(m: dict, root: Path, groups: list[str], seeds: list[int]) -> None:
    man, report = [], []
    for g in groups:
        for regime in m["regimes"][g]:
            for pid in m["policies"]:
                for pct in [0] if pid == "P0" else m["budgets_pct"]:
                    d = root / g / regime / f"b{pct:g}" / pid
                    have = sorted(d.glob("s*.json")) if d.exists() else []
                    got = {int(f.stem[1:]) for f in have}
                    missing = sorted(set(seeds) - got)
                    report.append(
                        {
                            "group": g,
                            "regime": regime,
                            "budget_pct": pct,
                            "policy": pid,
                            "done": len(got & set(seeds)),
                            "missing": len(missing),
                        }
                    )
                    if missing:
                        continue
                    rows = [flatten(json.loads(f.read_text())) for f in have]
                    df = pd.DataFrame(rows).sort_values("seed")
                    df = df[df["seed"].isin(seeds)]
                    out = root / g / f"{regime}_b{pct:g}_{pid}.parquet"
                    df.to_parquet(out, index=False)
                    man.append({"file": str(out.relative_to(ROOT)), "sha256": sha256_file(out)})
    rep = pd.DataFrame(report)
    rep.to_csv(root / "completeness.csv", index=False)
    if man:
        pd.DataFrame(man).to_csv(root / "manifest.csv", index=False)
    done = int((rep["missing"] == 0).sum())
    log(f"cells complete: {done} of {len(rep)}; runs missing: {int(rep['missing'].sum())}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--phase", required=True, choices=["cards", "tune", "run", "collect"])
    ap.add_argument("--groups", nargs="+", default=["A", "E"])
    ap.add_argument("--seeds", default="1-30")
    ap.add_argument("--shard")
    ap.add_argument("--family", default="eval")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    m = load_matrix()
    root = ROOT / "results" / ("dryrun" if a.dry_run else "raw")
    if a.phase == "cards":
        phase_cards(m)
    elif a.phase == "tune":
        phase_tune(m, root, a.groups, a.shard, a.dry_run)
    elif a.phase == "run":
        phase_run(m, root, a.groups, seed_range(a.seeds), a.shard, a.family)
    else:
        phase_collect(m, root, a.groups, seed_range(a.seeds))


if __name__ == "__main__":
    main()
