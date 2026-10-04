"""Week 19, task 4: protocol failures, not results (PROTOCOL.md v1.0 section 5).

Checks, without looking at any comparison:
  completeness  every cell (regime, budget, policy) has every eval seed (completeness.csv)
  overspend     no run spent more than its daily budget (a run that did is invalid)
  provenance    the git SHAs and code versions the records were produced with
  invariants    a sample re-run with the engine's invariant checks on (check=True): seed 1 of
                every regime, P2 and P4 at 2%; any InvariantError is a bug to fix and log in
                CHANGES_AFTER_FREEZE.md, after which every policy of that (regime, seed) is rerun
Writes results/summary/protocol_check.json. Exit code 1 if anything fails.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("rm", ROOT / "scripts/v2/24_run_matrix.py")
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)
from vmsim import engine, scenarios, worlds  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--groups", nargs="+", default=["A", "E", "B", "C", "D"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-rerun", action="store_true")
    a = ap.parse_args()
    m = rm.load_matrix()
    root = ROOT / "results" / ("dryrun" if a.dry_run else "raw")
    out = ROOT / "results" / ("dryrun_summary" if a.dry_run else "summary")
    out.mkdir(parents=True, exist_ok=True)
    groups = [g for g in a.groups if (root / g).exists()]
    comp = pd.read_csv(root / "completeness.csv")
    comp = comp[comp.group.isin(groups)]
    parts = [pd.read_parquet(f) for g in groups for f in sorted((root / g).glob("*.parquet"))]
    d = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    res = {
        "groups": groups,
        "cells": int(len(comp)),
        "cells_incomplete": comp[comp.missing > 0][
            ["regime", "budget_pct", "policy", "missing"]
        ].to_dict(orient="records"),
        "runs": int(len(d)),
        "overspend_runs": int(d["overspend"].sum()) if len(d) else 0,
        "git_shas": sorted(set(d["git_sha"])) if len(d) else [],
        "invariant_reruns": [],
    }
    if not a.no_rerun:
        for g in groups:
            for regime in m["regimes"][g]:
                cfg = scenarios.regime(rm.base_config(m), regime)
                prep = engine.prepare(worlds.generate(cfg, 1), cfg)
                kind = m["predictor_by_regime"].get(regime, m["predictor"])
                for pid in ("P2", "P4"):
                    tune = (
                        json.loads(rm.tune_path(root, regime, 2).read_text())
                        if pid == "P2"
                        else None
                    )
                    pol = rm.make_policy(pid, m, tune)
                    pred = (
                        engine.make_predictor(prep, kind, gamma=0.7) if kind != "oracle" else None
                    )
                    try:
                        engine.run(prep, pol, predictor=pred, budget_frac=0.02, check=True)
                        ok, err = True, None
                    except engine.InvariantError as e:
                        ok, err = False, str(e)
                    res["invariant_reruns"].append(
                        {"regime": regime, "policy": pid, "ok": ok, "error": err}
                    )
                    print(regime, pid, "ok" if ok else err, flush=True)
    res["passed"] = bool(
        not res["cells_incomplete"]
        and res["overspend_runs"] == 0
        and all(r["ok"] for r in res["invariant_reruns"])
    )
    (out / "protocol_check.json").write_text(json.dumps(res, indent=1))
    print(
        "passed" if res["passed"] else "FAILED",
        {k: res[k] for k in ("cells", "runs", "overspend_runs")},
    )
    sys.exit(0 if res["passed"] else 1)


if __name__ == "__main__":
    main()
