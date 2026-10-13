"""Exploratory diagnosis (post-freeze, 5 Oct 2026 onwards): why does P5 save more than BAM?

Week 18 found the Narya-inspired P5 ahead of BAM against never migrating in every A and E cell,
with about 34x fewer migrations (docs/v2/RESULTS_W18.md). P5 has one action no other policy has:
it can mark a flagged host avoid-allocation, so new VMs go elsewhere at no GB cost. This script
separates the two candidate explanations on dev seeds (never the evaluation seeds):

  avoid-allocation   P0+avoid (marks only), P4+avoid (BAM plus the same marks), P5-noavoid (P5
                     with its marks switched off)
  option to wait     P4-wait7, P4-wait1 (BAM judging each move over 7 or 1 days)
  guard fallback     P6-P0 (the guard falling back to never migrating instead of P2)

Every run uses the frozen matrix's scale, oracle predictor and a 2% budget. Writes
results/v2/diag_p5_vs_bam.json and prints each policy's mean saving against P0.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmsim import engine, scenarios, worlds  # noqa: E402
from vmsim.config import SimConfig  # noqa: E402
from vmsim.policies.bam import BAM  # noqa: E402
from vmsim.policies.guard import SafeGuard  # noqa: E402
from vmsim.policies.narya import Narya  # noqa: E402
from vmsim.policies.reference import Never  # noqa: E402
from vmsim.policies.variants import AvoidTop, BAMAvoid, BAMWait  # noqa: E402

M = yaml.safe_load((ROOT / "configs/v2/matrix.yaml").read_text())


class NaryaNoAvoid(Narya):
    """P5 with its avoid-allocation marks switched off (its actions otherwise unchanged)."""

    def avoid(self, obs):
        return None


def policies() -> dict:
    k = dict(M["p6"])
    k["slope_band"] = tuple(k["slope_band"])
    return {
        "P0": lambda: Never(),
        "P4": lambda: BAM(),
        "P5": lambda: Narya("faithful", name="P5"),
        "P5-noavoid": lambda: NaryaNoAvoid("faithful", name="P5-noavoid"),
        "P0+avoid": lambda: AvoidTop(0.02),
        "P4+avoid": lambda: BAMAvoid(0.02),
        "P4-wait7": lambda: BAMWait(7),
        "P4-wait1": lambda: BAMWait(1),
        "P6-P0": lambda: SafeGuard(Never(), BAM(), name="P6-P0", **k),
    }


def one(args: tuple[str, int, float]) -> list[dict]:
    regime, seed, pct = args
    s = M["scale"]
    base = SimConfig(
        n_hosts=s["n_hosts"],
        horizon_days=s["horizon_days"],
        warmup_days=s["warmup_days"],
        risk_h_days=s["risk_h_days"],
        name="matrix",
    )
    cfg = scenarios.regime(base, regime)
    prep = engine.prepare(worlds.generate(cfg, seed), cfg)
    out = []
    for pid, make in policies().items():
        t = time.time()
        r = engine.run(prep, make(), budget_frac=0.0 if pid == "P0" else pct / 100)
        out.append(
            {
                "regime": regime,
                "seed": seed,
                "policy": pid,
                "total_cost": float(r["cost_total"]),
                "interruption_cost": float(
                    r["cost_interrupt_resident"] + r["cost_interrupt_transient"]
                ),
                "migration_cost": float(r["cost_migration"]),
                "migrations": int(r["migrations"]),
                "unnecessary_migrations": int(r.get("migrations_unnecessary", 0)),
                "rejected_arrivals": int(r["rejected_arrivals"]),
                "seconds": round(time.time() - t, 1),
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--regimes", nargs="+", default=["A1", "A3", "E1"])
    ap.add_argument("--seeds", default="101-105", help="dev seeds only")
    ap.add_argument("--budget", type=float, default=2.0)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    lo, hi = map(int, a.seeds.split("-"))
    dev = M["seeds"]["dev"]
    if lo < dev[0] or hi > dev[1]:
        raise SystemExit(f"dev seeds only ({dev[0]}-{dev[1]})")
    jobs = [(r, s, a.budget) for r in a.regimes for s in range(lo, hi + 1)]
    rows = []
    with ProcessPoolExecutor(a.workers) as ex:
        for part in ex.map(one, jobs):
            rows += part
    out = ROOT / "results" / "v2" / "diag_p5_vs_bam.json"
    summary = {}
    for reg in a.regimes:
        p0 = [r for r in rows if r["regime"] == reg and r["policy"] == "P0"]
        base = {r["seed"]: r["total_cost"] for r in p0}
        summary[reg] = {}
        for pid in policies():
            sel = [r for r in rows if r["regime"] == reg and r["policy"] == pid]
            sv = np.array([(base[r["seed"]] - r["total_cost"]) / base[r["seed"]] for r in sel])
            summary[reg][pid] = {
                "saving_vs_p0_mean": float(sv.mean()),
                "saving_vs_p0_min": float(sv.min()),
                "saving_vs_p0_max": float(sv.max()),
                "migrations_mean": float(np.mean([r["migrations"] for r in sel])),
                "rejected_arrivals_mean": float(np.mean([r["rejected_arrivals"] for r in sel])),
            }
    out.write_text(
        json.dumps(
            {
                "note": "exploratory, post-freeze; dev seeds; oracle predictor; "
                f"budget {a.budget}%; saving = (C_P0 - C) / C_P0",
                "seeds": [lo, hi],
                "summary": summary,
                "runs": rows,
            },
            indent=1,
        )
    )
    for reg, d in summary.items():
        print(f"== {reg} (seeds {lo}-{hi}, {a.budget}% budget)")
        for pid, x in d.items():
            print(
                f"  {pid:11} {100 * x['saving_vs_p0_mean']:+6.1f}% "
                f"[{100 * x['saving_vs_p0_min']:+.1f}, {100 * x['saving_vs_p0_max']:+.1f}]  "
                f"migrations {x['migrations_mean']:8.0f}  "
                f"rejected {x['rejected_arrivals_mean']:6.0f}"
            )
    print("->", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
