"""Week 28, task 3: every paper number that changed between two versions of paper/numbers.tex.

Prints each macro whose value changed, with the old and new value and, where both are numbers,
the difference; then macros added and removed. Placeholders ("??") filled in by new results are
listed separately. Paste the markdown output (--md) into docs/v2/LOG.md with the commit range.

  .venv/bin/python scripts/v2/42_numbers_diff.py                 # HEAD vs the working tree
  .venv/bin/python scripts/v2/42_numbers_diff.py v2.0-rc2 HEAD   # any two git revisions
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = "paper/numbers.tex"
MACRO = re.compile(r"\\newcommand\{\\(V[A-Za-z]+)\}\{(.*)\\xspace\}")
PLACEHOLDER = r"\textbf{??}"


def read(rev: str | None) -> dict[str, str]:
    """Macros at a git revision, or in the working tree when rev is None."""
    if rev is None:
        text = (ROOT / PATH).read_text()
    else:
        r = subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{rev}:{PATH}"], capture_output=True, text=True
        )
        if r.returncode:
            raise SystemExit(f"cannot read {PATH} at {rev}: {r.stderr.strip()}")
        text = r.stdout
    return {m.group(1): m.group(2) for m in map(MACRO.match, text.splitlines()) if m}


def number(s: str) -> float | None:
    t = s.replace("{,}", "").replace(",", "").replace("\\%", "").strip()
    try:
        return float(t)
    except ValueError:
        return None


def diff(old: dict[str, str], new: dict[str, str]) -> dict[str, list]:
    out = {"changed": [], "filled": [], "added": [], "removed": []}
    for k in sorted(old.keys() & new.keys()):
        a, b = old[k], new[k]
        if a == b:
            continue
        if a == PLACEHOLDER:
            out["filled"].append((k, b))
        else:
            x, y = number(a), number(b)
            out["changed"].append((k, a, b, None if x is None or y is None else y - x))
    out["added"] = [(k, new[k]) for k in sorted(new.keys() - old.keys())]
    out["removed"] = [(k, old[k]) for k in sorted(old.keys() - new.keys())]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("old", nargs="?", default="HEAD")
    ap.add_argument("new", nargs="?", default=None, help="a git revision; default the working tree")
    ap.add_argument("--md", action="store_true", help="markdown, for docs/v2/LOG.md")
    a = ap.parse_args()
    d = diff(read(a.old), read(a.new))
    label = f"{a.old} → {a.new or 'working tree'}"
    if a.md:
        print(f"Number diff {label}: {len(d['changed'])} changed, {len(d['filled'])} filled, "
              f"{len(d['added'])} added, {len(d['removed'])} removed\n")
        if d["changed"]:
            print("| Macro | Old | New | Difference |\n| --- | --- | --- | --- |")
            for k, x, y, dd in d["changed"]:
                print(f"| `\\{k}` | {x} | {y} | {'' if dd is None else f'{dd:+g}'} |")
        return
    print(label)
    for k, x, y, dd in d["changed"]:
        print(f"  changed  {k}: {x} -> {y}" + ("" if dd is None else f"  ({dd:+g})"))
    for name, rows in (("filled", d["filled"]), ("added", d["added"]), ("removed", d["removed"])):
        for k, v in rows:
            print(f"  {name:8} {k} = {v}")
    n = sum(len(v) for v in d.values())
    print(f"{n} differences" if n else "no differences")


if __name__ == "__main__":
    main()
