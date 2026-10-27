"""Builds webapp/brain.json, the records the site's Brain page answers from.

The Brain only repeats what the project's own records say: the claims ledger (docs/v2/CLAIMS_LEDGER.md) and
the decision records (docs/v2/DECISIONS/ADR-*.md). This script reads them from a v2 checkout, keeps their
wording, strips markdown and LaTeX macro names, and records the commit it read, so every answer can say where
it came from. Rerun it whenever those documents change:

    python3 scripts/build_brain.py --docs ~/Desktop/ccproject/docs/v2
"""
import argparse
import json
import re
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "webapp" / "brain.json"

# the section labels the decision records use ("Context:", "Context.", "Decision (proposed):", "## Result", ...)
SECTION = re.compile(r"^(?:##\s+)?(Context|Decision|Why|Alternatives considered|Alternatives|Consequences|Cost|Script|Implementation|Result)\b[^\n:.]*[:.]?\s*(.*)$")
KEY = {"Context": "context", "Decision": "decision", "Why": "why", "Alternatives considered": "alternatives", "Alternatives": "alternatives",
       "Consequences": "consequences", "Cost": "cost", "Script": "notes", "Implementation": "implementation", "Result": "result"}


def clean(text):
    """Plain text: no backticks, bold, links or LaTeX macro names; escaped pipes restored."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"`?\\V[A-Za-z]+`?", "", text)                  # \VGOneMaxAbsTauB and friends: generated numbers
    text = text.replace("`", "").replace("**", "").replace("\\|", "|")
    text = re.sub(r"\s+;", ";", re.sub(r"[ \t]+", " ", text))
    return text.strip(" ;,")


def claims(ledger):
    rows = []
    for line in ledger.read_text().splitlines():
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cells) >= 7 and re.fullmatch(r"C\d+[a-z]?", cells[0]):
            cid, claim, evidence, size, family, caveat, status = cells[:7]
            rows.append({"id": cid, "kind": "claim", "title": clean(claim), "evidence": clean(evidence), "size": clean(size),
                         "family": clean(family), "caveat": clean(caveat), "status": clean(status)})
    return rows


def decisions(folder):
    out = []
    for f in sorted(folder.glob("ADR-*.md")):
        lines = f.read_text().splitlines()
        head = re.match(r"#\s*(ADR-\d+):\s*(.*)", lines[0])
        rec = {"id": head.group(1), "kind": "decision", "title": clean(head.group(2)), "status": "", "date": "", "file": f.name}
        cur, buf = "context", {}
        for line in lines[1:]:
            if line.startswith("Status:"):
                rec["status"] = clean(line[7:])
                continue
            if line.startswith("Date:"):
                rec["date"] = line[5:].strip()
                continue
            m = SECTION.match(line)
            if m:
                cur = KEY[m.group(1)]
                line = m.group(2)
            if line.strip():
                buf.setdefault(cur, []).append(line.strip())
        for k, parts in buf.items():
            items = [clean(p[2:]) for p in parts if p.startswith(("- ", "* "))]
            text = clean(" ".join(p for p in parts if not p.startswith(("- ", "* "))))
            rec[k] = {"text": text, "items": items} if items else {"text": text, "items": []}
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--docs", required=True, type=Path, help="the docs/v2 folder of a v2 checkout")
    a = ap.parse_args()
    docs = a.docs.expanduser()
    try:
        commit = subprocess.run(["git", "-C", str(docs), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        branch = subprocess.run(["git", "-C", str(docs), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit, branch = "unknown", "unknown"
    data = {"built": date.today().isoformat(), "source": f"{branch}@{commit}",
            "claims": claims(docs / "CLAIMS_LEDGER.md"), "decisions": decisions(docs / "DECISIONS")}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    print(f"{OUT.relative_to(ROOT)}: {len(data['claims'])} claims, {len(data['decisions'])} decisions from {data['source']}")


if __name__ == "__main__":
    main()
