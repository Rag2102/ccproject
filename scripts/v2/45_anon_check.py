"""Week 36: nothing in the submission or its links identifies the authors.

Identity terms are collected at run time, never typed into this file: the authors in CITATION.cff
and .zenodo.json, git's user.name and user.email, the GitHub owner and repository from the remote,
and the live demo's host; `--term` adds more. Then it checks:

  paper    paper/*.tex, paper/sections/*.tex, paper/refs.bib: no term (FAIL)
  pdf      paper/main.pdf if built: no term in the text, and empty Author/Creator fields that name
           no one (pdfinfo; exiftool too when installed) (FAIL)
  figures  every PDF and PNG in results/figures: no term in the metadata (FAIL)
  console  console/data/console.json built with --anonymous: no SHA, no demo link, no term (FAIL;
           skipped with a note when the current build is not the anonymous one)
  repo     every tracked file: which ones contain a term. Not a failure (the repository is not
           the submission), but these are the files the anonymous repository view must hide or
           rewrite; --repo-strict makes them failures, e.g. for a checked anonymised export.

  .venv/bin/python scripts/v2/45_anon_check.py               # report; exit 1 on any FAIL
  .venv/bin/python scripts/v2/45_anon_check.py --root /path/to/anonymised/export --repo-strict
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def sh(*cmd: str, cwd: Path = ROOT) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd).stdout.strip()
    except OSError:
        return ""


def terms(root: Path, extra: list[str]) -> list[str]:
    t: set[str] = set(extra)
    cff = root / "CITATION.cff"
    if cff.exists():
        for a in yaml.safe_load(cff.read_text()).get("authors", []):
            t |= {a.get("family-names", ""), a.get("given-names", ""), a.get("email", "")}
            t.add(a.get("affiliation", ""))
    z = root / ".zenodo.json"
    if z.exists():
        for c in json.loads(z.read_text()).get("creators", []):
            t |= {c.get("affiliation", ""), *c.get("name", "").replace(",", " ").split()}
    t |= {sh("git", "config", "user.name"), sh("git", "config", "user.email")}
    t |= set(sh("git", "config", "user.name").split())
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", sh("git", "remote", "get-url", "origin"))
    if m:
        t |= {m.group(1), f"{m.group(1)}/{m.group(2)}"}
    t.add("onrender.com")
    return sorted({x.strip() for x in t if x and len(x.strip()) >= 3}, key=str.lower)


def find(text: str, ts: list[str]) -> list[str]:
    low = text.lower()
    return [
        x for x in ts if re.search(r"(?<![a-z0-9])" + re.escape(x.lower()) + r"(?![a-z0-9])", low)
    ]


def pdf_meta(p: Path) -> str:
    out = sh("pdfinfo", str(p)) if shutil.which("pdfinfo") else ""
    if shutil.which("exiftool"):
        out += "\n" + sh("exiftool", "-a", "-G1", str(p))
    return out


def png_meta(p: Path) -> str:
    try:
        from PIL import Image

        return "\n".join(f"{k}: {v}" for k, v in Image.open(p).info.items() if isinstance(v, str))
    except Exception:  # noqa: BLE001 - unreadable image: nothing to report
        return ""


def office_text(p: Path) -> str:
    """Author metadata and text of a .docx, .pptx or .xlsx (zipped XML)."""
    import zipfile

    try:
        with zipfile.ZipFile(p) as z:
            names = [n for n in z.namelist() if n.endswith(".xml")]
            return "\n".join(z.read(n).decode("utf-8", "ignore") for n in names)
    except (zipfile.BadZipFile, OSError):
        return ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT, help="tree to check (default: this repo)")
    ap.add_argument("--term", action="append", default=[], help="extra identity term")
    ap.add_argument("--repo-strict", action="store_true", help="tracked-file hits are failures")
    a = ap.parse_args()
    root = a.root.resolve()
    ts = terms(ROOT, a.term)
    fails, notes = [], []
    print(f"{len(ts)} identity terms (from CITATION.cff, .zenodo.json, git config and the remote)")

    for p in [
        root / "paper" / "main.tex",
        *sorted((root / "paper").glob("**/*.tex")),
        root / "paper" / "refs.bib",
    ]:
        if p.exists() and (hit := find(p.read_text(errors="ignore"), ts)):
            fails.append(f"paper   {p.relative_to(root)}: {len(hit)} term(s)")

    pdf = root / "paper" / "main.pdf"
    if pdf.exists():
        txt = sh("pdftotext", str(pdf), "-") if shutil.which("pdftotext") else ""
        if hit := find(txt, ts):
            fails.append(f"pdf     main.pdf text: {len(hit)} term(s)")
        if hit := find(pdf_meta(pdf), ts):
            fails.append(f"pdf     main.pdf metadata: {len(hit)} term(s)")
    else:
        notes.append("pdf     paper/main.pdf not built (make paper needs LaTeX): skipped")

    for p in sorted((root / "results" / "figures").glob("*")):
        meta = pdf_meta(p) if p.suffix == ".pdf" else png_meta(p) if p.suffix == ".png" else ""
        if meta and (hit := find(meta, ts)):
            fails.append(f"figure  {p.name} metadata: {len(hit)} term(s)")

    cj = root / "console" / "data" / "console.json"
    if cj.exists():
        d = json.loads(cj.read_text())
        if not d.get("meta", {}).get("anonymous"):
            notes.append("console current build is not anonymous (make console-anon): skipped")
        else:
            if d["meta"].get("git_sha") != "anonymised" or d["meta"].get("policy_lab_url"):
                fails.append("console meta keeps the commit or the demo link")
            text = cj.read_text() + (root / "console" / "index.html").read_text()
            if hit := find(text, ts):
                fails.append(f"console {len(hit)} term(s) in the anonymous build")

    files = (
        sh("git", "ls-files", cwd=root).splitlines()
        if (root / ".git").exists()
        else [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()]
    )
    repo_hits = []
    for f in files:
        p = root / f
        if p.suffix in (".parquet", ".joblib", ".gz", ".zip", ".png", ".pdf") or not p.is_file():
            continue
        if p.stat().st_size > 2_000_000:
            continue
        text = (
            office_text(p)
            if p.suffix in (".docx", ".pptx", ".xlsx")
            else p.read_text(errors="ignore")
        )
        if find(text, ts):
            repo_hits.append(f)
    for f in repo_hits:
        (fails if a.repo_strict else notes).append(f"repo    {f}")

    for n in notes:
        print("note", n)
    for f in fails:
        print("FAIL", f)
    print(
        f"{len(fails)} failures; {len(repo_hits)} tracked files name the authors "
        "(hide or rewrite them in the anonymous repository view)"
    )
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
