"""Week 33, task 4: reporting audit. Every result number in the paper's text has an interval, n and
a family in the summary it comes from.

Lists every \\V macro used in paper/main.tex and paper/sections/*.tex, splits them into constants
(configuration and data counts) and results, and checks each result macro against the summary cell
that produced it (results/summary/*.json, indexed with 40_numbers.name so the names match):

  ci       the cell has a 95% interval (ci_bca or ci_bca_simultaneous)
  n        the cell states its number of seeds
  family   the cell says whether it is confirmatory, exploratory or descriptive
  paired   the paragraph that uses a point estimate also uses its interval macros (warning only)

A result macro whose summary does not exist yet is "pending" (a placeholder), not a failure.
Exit 1 if any present result macro misses ci, n or family. `--md` prints a table for the log.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUMM = ROOT / "results" / "summary"
_spec = importlib.util.spec_from_file_location("nums", ROOT / "scripts/v2/40_numbers.py")
NUMS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(NUMS)
name = NUMS.name

# result macros: prefix -> (summary prefix of the interval macros or None)
RESULT_PREFIX = {
    "Delta": ("CILo", "CIHi"),
    "SaveVsPZero": ("SaveVsPZeroLo", "SaveVsPZeroHi"),
    "CILo": None,
    "CIHi": None,
    "SaveVsPZeroLo": None,
    "SaveVsPZeroHi": None,
    "BeatsPZero": None,
    "SaveAvoid": ("SaveAvoidLo", "SaveAvoidHi"),
    "SaveAvoidLo": None,
    "SaveAvoidHi": None,
    "Holm": None,
    "Migrations": None,
    "Util": None,
}


def macros_in(paths: list[Path]) -> dict[str, list[tuple[str, int]]]:
    """macro -> [(file, paragraph index)]"""
    out: dict[str, list[tuple[str, int]]] = {}
    for p in paths:
        paras = re.split(r"\n\s*\n", p.read_text())
        for i, para in enumerate(paras):
            body = re.sub(r"(?<!\\)%.*", "", para)  # drop comments, keep \%
            for m in re.findall(r"\\(V[A-Za-z]+)", body):
                out.setdefault(m, []).append((p.name, i))
    return out


def index_cells() -> dict[str, dict]:
    """macro name -> {"file", "cell"}: the summary each macro family is generated from
    (40_numbers.py): confirmatory.json first, then the group files, for the comparisons against
    P2; vs_p0.json for the savings against never migrating."""
    idx: dict[str, dict] = {}
    srcs = {
        "p2": [SUMM / "confirmatory.json", *sorted(SUMM.glob("[A-E].json"))],
        "p0": [SUMM / "vs_p0.json"],
        "avoid": [SUMM / "explore_avoid.json"],
    }
    kind_of = {
        p: "avoid" if "Avoid" in p else "p0" if "PZero" in p else "p2" for p in RESULT_PREFIX
    }
    for kind, files in srcs.items():
        pres = [p for p in RESULT_PREFIX if kind_of[p] == kind]
        for f in files:
            if not f.exists():
                continue
            for c in json.loads(f.read_text())["cells"]:
                if kind == "avoid" and "avoid" not in c["policy"]:
                    continue  # explore_avoid.json also carries P4 and P5 for reference
                pol = c["policy"].split("+")[0]  # "P0+avoid" -> macro part "PZero"
                base = (pol, c["regime"].replace("-", ""), f"{float(c['budget_pct']):g}")
                for pre in pres:
                    idx.setdefault(name(pre, *base), {"file": f.name, "cell": c})
    return idx


def split_prefix(macro: str) -> str | None:
    body = macro[1:]
    for pre in sorted(RESULT_PREFIX, key=len, reverse=True):
        if body.startswith(pre) and re.match(r"P[A-Z]", body[len(pre) :]):
            return pre
    return None


def check(cell: dict) -> list[str]:
    miss = []
    if not (cell.get("ci_bca") or cell.get("ci_bca_simultaneous")):
        miss.append("ci")
    if not cell.get("n_seeds"):
        miss.append("n")
    if not cell.get("family"):
        miss.append("family")
    return miss


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--md", action="store_true")
    a = ap.parse_args()
    paths = [ROOT / "paper" / "main.tex"] + sorted((ROOT / "paper" / "sections").glob("*.tex"))
    used = macros_in(paths)
    defined, _ = NUMS.build()
    idx = index_cells()
    rows, bad = [], 0
    for m in sorted(used):
        pre = split_prefix(m)
        where = ", ".join(sorted({f for f, _ in used[m]}))
        if m not in defined:
            rows.append((m, "UNDEFINED", where, ""))
            bad += 1
            continue
        if pre is None:
            rows.append((m, "constant", where, ""))
            continue
        if defined[m] == NUMS.PLACEHOLDER:
            rows.append((m, "pending", where, "results not run yet"))
            continue
        hit = idx.get(m)
        if hit is None:
            rows.append((m, "FAIL", where, "no summary cell found"))
            bad += 1
            continue
        miss = check(hit["cell"])
        note = []
        pair = RESULT_PREFIX[pre]
        if pair:
            lo, hi = (m.replace(pre, p, 1) for p in pair)
            for f, i in used[m]:
                near = {x for x, places in used.items() if (f, i) in places}
                if not {lo, hi} <= near:
                    note.append(f"interval not in the same paragraph ({f})")
        status = "FAIL" if miss else ("warn" if note else "ok")
        bad += bool(miss)
        detail = "; ".join(([f"missing {', '.join(miss)}"] if miss else []) + note)
        rows.append((m, status, where, f"{hit['file']} {detail}".strip()))
    counts = {
        s: sum(r[1] == s for r in rows)
        for s in ("ok", "warn", "pending", "constant", "FAIL", "UNDEFINED")
    }
    if a.md:
        print("| Macro | Status | Used in | Note |\n| --- | --- | --- | --- |")
        for r in rows:
            print("| " + " | ".join(r) + " |")
    else:
        for r in rows:
            if r[1] not in ("constant", "ok"):
                print(f"{r[1]:9} {r[0]:40} {r[2]:30} {r[3]}")
    print(f"{len(rows)} macros in the text: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
