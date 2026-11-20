"""Rebuild results/raw/manifest.csv and completeness.csv from every main-matrix cell Parquet.

24_run_matrix.py --phase collect rewrites both files for the groups and regimes of that call only,
so the A3/A5 extension (ADR-007) leaves them listing 66 of 528 cells. This reads the cells and
changes none of them. Regimes the SD rule extended are expected at seeds 1-50, others at 1-30.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("rm", ROOT / "scripts/v2/24_run_matrix.py")
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)

RAW = ROOT / "results" / "raw"
EXTENDED = {"A3", "A5", "B1", "B2", "C"}


def main() -> None:
    m = rm.load_matrix(None)
    man, report = [], []
    for g in m["regimes"]:
        for regime in m["regimes"][g]:
            want = set(range(1, 51 if regime in EXTENDED else 31))
            for pid in m["policies"]:
                for pct in [0] if pid == "P0" else m["budgets_pct"]:
                    out = RAW / g / f"{regime}_b{pct:g}_{pid}.parquet"
                    got = set(pd.read_parquet(out, columns=["seed"])["seed"]) if out.exists() else set()
                    report.append(
                        {
                            "group": g,
                            "regime": regime,
                            "budget_pct": pct,
                            "policy": pid,
                            "done": len(got & want),
                            "missing": len(want - got),
                        }
                    )
                    if out.exists():
                        man.append(
                            {"file": str(out.relative_to(ROOT)), "sha256": rm.sha256_file(out)}
                        )
    rep = pd.DataFrame(report)
    rep.to_csv(RAW / "completeness.csv", index=False)
    pd.DataFrame(man).to_csv(RAW / "manifest.csv", index=False)
    print(f"cells {len(rep)}, runs {rep['done'].sum()}, missing {rep['missing'].sum()}")


if __name__ == "__main__":
    main()
