"""Week 32, task 4: the contribution map. Each contribution bullet in the introduction points to its
section, figure or table and to its claim in docs/v2/CLAIMS_LEDGER.md; a bullet without both is
to be dropped.

For every \\item of the first itemize after "contributions" in paper/sections/intro.tex:
  claim    at least one claim id (C1, C2a, ...) that has a row in the ledger         FAIL if none
  ref      at least one \\ref to a section, figure or table                          FAIL if none
  macros   every \\V macro it quotes is defined (paper/numbers.tex)                   FAIL
  status   the ledger status of each claim; "open" rows wait for runs                info

  .venv/bin/python scripts/v2/48_contribution_map.py [--md]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def ledger() -> dict[str, dict]:
    rows = {}
    for line in (ROOT / "docs" / "v2" / "CLAIMS_LEDGER.md").read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 7 and re.fullmatch(r"C\d+[a-z]?", cells[0]):
            rows[cells[0]] = {"claim": cells[1], "evidence": cells[2], "status": cells[-1]}
    return rows


def bullets() -> list[str]:
    t = (ROOT / "paper" / "sections" / "intro.tex").read_text()
    t = re.sub(r"(?<!\\)%.*", "", t)
    m = re.search(r"contributions.*?\\begin\{itemize\}(.*?)\\end\{itemize\}", t, re.S)
    return [b.strip() for b in m.group(1).split(r"\item")[1:]] if m else []


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--md", action="store_true")
    a = ap.parse_args()
    led = ledger()
    defined = set(
        re.findall(r"\\newcommand\{\\(V[A-Za-z]+)\}", (ROOT / "paper/numbers.tex").read_text())
    )
    rows, bad = [], 0
    for b in bullets():
        title = re.search(r"\\textbf\{([^}]*)\}", b)
        name = title.group(1) if title else b[:50]
        ids = re.findall(r"\b(C\d+[a-z]?)\b", b)
        refs = re.findall(r"\\(?:ref|Cref|cref|autoref)\{([^}]*)\}", b)
        macros = re.findall(r"\\(V[A-Za-z]+)", b)
        claims = [i for i in ids if i in led or any(k.startswith(i) for k in led)]
        status = "; ".join(
            f"{k}: {led[k]['status']}"
            for i in claims
            for k in led
            if k == i or (k.startswith(i) and k[len(i) :].isalpha())
        )
        probs = []
        if not claims:
            probs.append("no ledger claim")
        if not refs:
            probs.append("no section, figure or table reference")
        if undefined := [m for m in macros if m not in defined]:
            probs.append("undefined " + ", ".join(undefined))
        bad += bool(probs)
        rows.append(
            (name, ", ".join(ids) or "-", ", ".join(refs) or "-", "; ".join(probs) or "ok", status)
        )
    if a.md:
        print("| Contribution | Claims | Points to | Check | Ledger status |")
        print("| --- | --- | --- | --- | --- |")
        for r in rows:
            print("| " + " | ".join(r) + " |")
    else:
        for r in rows:
            print(f"{r[3]:4} {r[0]}\n     claims {r[1]}; refs {r[2]}\n     {r[4]}")
    print(f"{len(rows)} contribution bullets, {bad} to fix")
    sys.exit(1 if bad or not rows else 0)


if __name__ == "__main__":
    main()
