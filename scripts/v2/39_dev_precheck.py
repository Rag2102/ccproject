"""Week 30, task 4: a new scenario's dev-seed pre-check, before any evaluation seed is run.

For each scenario (e.g. B1@G0-low, a cost-range setting, or a new placement cell) and its base
regime, run P0 and BAM (P4) on dev seeds (101-110 by default) and report what the plan asks to
check first: the engine's invariants (it raises on any violation), budget utilisation, host
failures and interrupted VMs per run, migrations, and the saving against never migrating. A
scenario passes when no invariant fails, every run has failures to mitigate, and utilisation is
within [0, 1]. Dev seeds only; nothing here touches the evaluation seeds.

  .venv/bin/python scripts/v2/39_dev_precheck.py B1@G0-low B1@G0-high --budget 2
  .venv/bin/python scripts/v2/39_dev_precheck.py B1-f --seeds 101-103

Writes results/v2/precheck_<scenario>.json and exits 1 if any scenario fails.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmsim import engine, scenarios, worlds  # noqa: E402
from vmsim.policies.bam import BAM  # noqa: E402
from vmsim.policies.reference import Never  # noqa: E402

_spec = importlib.util.spec_from_file_location("rm", ROOT / "scripts/v2/24_run_matrix.py")
RM = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RM)
M = RM.load_matrix()


def one(job: tuple[str, int, float]) -> dict:
    cell, seed, pct = job
    cfg = scenarios.regime(RM.base_config(M), cell)
    prep = engine.prepare(worlds.generate(cfg, seed), cfg)
    out = {"scenario": cell, "seed": seed}
    try:
        p0 = engine.run(prep, Never(), budget_frac=0.0)
        p4 = engine.run(prep, BAM(), budget_frac=pct / 100)
    except engine.InvariantError as e:
        return {**out, "invariant_error": str(e)}
    return {
        **out,
        "host_failures": int(p0["host_failures"]),
        "interrupted_vms_p0": int(p0["interrupted_vms"]),
        "migrations_p4": int(p4["migrations"]),
        "utilisation_p4": float(p4["budget_utilisation"]),
        "saving_p4_vs_p0": float((p0["cost_total"] - p4["cost_total"]) / p0["cost_total"]),
        "rejected_arrivals_p0": int(p0["rejected_arrivals"]),
    }


def verdict(rows: list[dict]) -> tuple[bool, list[str]]:
    why = [f"seed {r['seed']}: {r['invariant_error']}" for r in rows if "invariant_error" in r]
    ok = [r for r in rows if "invariant_error" not in r]
    why += [f"seed {r['seed']}: no host failures" for r in ok if r["host_failures"] == 0]
    why += [
        f"seed {r['seed']}: utilisation {r['utilisation_p4']:.3f} outside [0, 1]"
        for r in ok
        if not 0 <= r["utilisation_p4"] <= 1 + 1e-9
    ]
    return not why, why


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("scenarios", nargs="+")
    ap.add_argument("--seeds", default="101-110", help="dev seeds only")
    ap.add_argument("--budget", type=float, default=2.0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--no-base", action="store_true", help="skip the base regime for comparison")
    a = ap.parse_args()
    seeds = RM.seed_range(a.seeds)
    dev = M["seeds"]["dev"]
    if min(seeds) < dev[0] or max(seeds) > dev[1]:
        raise SystemExit(f"dev seeds only ({dev[0]}-{dev[1]})")
    cells = list(dict.fromkeys(a.scenarios))
    if not a.no_base:
        cells += [
            b for b in dict.fromkeys(scenarios.split_cost(c)[0] for c in cells) if b not in cells
        ]
    for c in cells:  # fail fast on an unknown regime or an underived cost setting
        try:
            scenarios.regime(RM.base_config(M), c)
        except ValueError as e:
            raise SystemExit(f"{c}: {e}") from None
    jobs = [(c, s, a.budget) for c in cells for s in seeds]
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(one, jobs))
    failed = False
    for c in cells:
        rs = [r for r in rows if r["scenario"] == c]
        ok, why = verdict(rs)
        good = [r for r in rs if "invariant_error" not in r]
        mean = (
            {
                k: float(np.mean([r[k] for r in good]))
                for k in good[0]
                if k not in ("scenario", "seed")
            }
            if good
            else {}
        )
        rep = {
            "scenario": c,
            "seeds": a.seeds,
            "budget_pct": a.budget,
            "pass": ok,
            "problems": why,
            "mean": mean,
            "runs": rs,
        }
        out = ROOT / "results" / "v2" / f"precheck_{c.replace('@', '_')}.json"
        out.write_text(json.dumps(rep, indent=1))
        line = " ".join(f"{k} {v:.3g}" for k, v in mean.items())
        print(f"{'PASS' if ok else 'FAIL'} {c:14} {line}")
        for w in why:
            print("   ", w)
        failed |= not ok and c in a.scenarios
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
