"""Weeks 34 and 37: refs.bib hygiene before submission.

Checks every entry of paper/refs.bib (offline; it never looks anything up):

  unverified   no `note` recording how it was checked (the Week 24 rule: checked against the
               publisher page or the paper before it enters refs.bib)            FAIL
  required     missing author/title/year, or venue (booktitle/journal) for papers  FAIL
  uncited      in refs.bib but not cited in the paper                              warn
  missing      cited in the paper but not in refs.bib                              FAIL
  arxiv        an arXiv-only (@misc) entry whose note names a venue: replace it with the
               published version when that exists (Week 37, task 4)                todo
  doi          a conference or journal paper without a DOI (USENIX gives none:
               not flagged when the url is usenix.org, or when the note says
               "No DOI" and how that was checked)                                  todo
  venue        the same venue acronym written in different ways, ignoring the
               edition, year, volume, track and "International"                    todo

  .venv/bin/python scripts/v2/46_refs_check.py         # exit 1 on any FAIL
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIB = ROOT / "paper" / "refs.bib"
VENUE_HINT = re.compile(
    r"\b(NeurIPS|ICML|ICLR|EuroSys|OSDI|NSDI|SOSP|SoCC|ATC|TMLR|KDD|SIGMETRICS|DSN|ICPE|CLOUD)\b"
)
ACRONYM = re.compile(r"\(([A-Za-z]+)\s*'?\d{2,4}\)|\b(OSDI|NSDI|SOSP|SoCC|EuroSys|ATC|KDD|DSN)\b")
# what differs between editions of one venue: "28th", "Twentieth", "'22", "2019", a volume
# number ("Systems 32"), "International", a named track
ORDINAL = r"(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth)"
EDITION = re.compile(
    rf"\b(\d+(st|nd|rd|th)|(\w+-)?({ORDINAL}|\w*teenth|\w*tieth))\s+|\s*'\d{{2}}|\s\d{{4}}(?=\))"
    r"|(?<=[a-z])\s\d+(?=\s\()|International\s+|,\s[^,]*Track$",
    re.I,
)


def entries(text: str) -> dict[str, dict]:
    out = {}
    for m in re.finditer(r"@(\w+)\{([^,]+),(.*?)\n\}", text, re.S):
        kind, key, body = m.group(1).lower(), m.group(2).strip(), m.group(3)
        fields = {
            f.lower(): v.strip()
            for f, v in re.findall(r"(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}", body)
        }
        out[key] = {"kind": kind, **fields}
    return out


def cited() -> set[str]:
    keys: set[str] = set()
    for p in [ROOT / "paper" / "main.tex", *sorted((ROOT / "paper" / "sections").glob("*.tex"))]:
        for group in re.findall(r"\\cite[pt]?\*?(?:\[[^\]]*\])?\{([^}]*)\}", p.read_text()):
            keys |= {k.strip() for k in group.split(",") if k.strip()}
    return keys


def main() -> None:
    e = entries(BIB.read_text())
    used = cited()
    fail, warn, todo = [], [], []
    for key, f in sorted(e.items()):
        if not f.get("note"):
            fail.append(f"unverified  {key}: no note on how it was checked")
        # @misc (datasets, software) may lack a year: refs.bib leaves out fields it could not check
        need = ["title"] + (["author", "year"] if f["kind"] != "misc" else [])
        if f["kind"] == "misc" and not f.get("year"):
            todo.append(f"year        {key}: no year (add the version or access year)")
        if f["kind"] in ("inproceedings", "article"):
            need.append("booktitle" if f["kind"] == "inproceedings" else "journal")
        miss = [x for x in need if not f.get(x)]
        if miss and not (f.get("archiveprefix") == "arXiv" and miss == ["journal"]):
            fail.append(f"required    {key}: missing {', '.join(miss)}")
        if key not in used:
            warn.append(f"uncited     {key}")
        if f["kind"] == "misc" and (
            f.get("archiveprefix") == "arXiv" or "arxiv.org" in f.get("url", "")
        ):
            if VENUE_HINT.search(f.get("note", "")):
                todo.append(
                    f"arxiv       {key}: the note names a venue; cite the published version"
                )
        if (
            f["kind"] in ("inproceedings", "article")
            and not f.get("doi")
            and "usenix.org" not in f.get("url", "")
            and f.get("archiveprefix") != "arXiv"
            and "No DOI" not in f.get("note", "")
        ):
            todo.append(f"doi         {key}: no DOI")
    for key in sorted(used - set(e)):
        fail.append(f"missing     {key}: cited but not in refs.bib")
    forms = defaultdict(set)
    for f in e.values():
        venue = f.get("booktitle") or f.get("journal") or ""
        m = ACRONYM.search(venue)
        if m:
            forms[(m.group(1) or m.group(2)).upper()].add(re.sub(EDITION, "", venue))
    for acr, vs in sorted(forms.items()):
        if len(vs) > 1:
            todo.append(f"venue       {acr} written {len(vs)} ways: " + " | ".join(sorted(vs)))
    for lines, tag in ((fail, "FAIL"), (warn, "warn"), (todo, "todo")):
        for x in lines:
            print(tag, x)
    print(
        f"{len(e)} entries, {len(used)} cited: {len(fail)} fail, {len(warn)} uncited, "
        f"{len(todo)} to do before submission"
    )
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
