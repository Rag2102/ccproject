"""Week 39, task 3: the supplementary zip, anonymous and within the venue's size limit.

Stages, in a scratch directory:
  README.md            what is inside, and the anonymous artifact link (--artifact-url)
  console/             the double-blind Console build (41_console_data.py --anonymous); the
                       repository's own console/data is rebuilt normally afterwards
  summaries/           results/summary/*.json (every number in the paper comes from these)
  figures/             the catalogued figures whose result file exists (catalogue.yaml)
  tables/              paper/tables/*.tex
  paper.pdf            paper/main.pdf, if it has been built
then runs 45_anon_check.py on the staged tree with every hit a failure, and writes
results/final/supplementary.zip only if that passes and the zip is within --max-mb.

  .venv/bin/python scripts/v2/47_supplementary.py --artifact-url https://anonymous.4open.science/r/...
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PY = str(ROOT / ".venv" / "bin" / "python")


def run(*args: str) -> None:
    subprocess.run([PY, *args], check=True, cwd=ROOT, stdout=subprocess.DEVNULL)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--artifact-url", default="(anonymous artifact link: added at submission)")
    ap.add_argument("--max-mb", type=float, default=50.0)
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        st = Path(tmp) / "supplementary"
        st.mkdir()
        try:
            run("scripts/v2/41_console_data.py", "--anonymous")
            shutil.copytree(
                ROOT / "console", st / "console", ignore=shutil.ignore_patterns("README.md")
            )
        finally:
            run("scripts/v2/41_console_data.py")  # the repository keeps its normal build
        # figures: only catalogued ones whose result file exists (no stale or dry-run copies)
        (st / "figures").mkdir()
        for f in yaml.safe_load((ROOT / "results/figures/catalogue.yaml").read_text()):
            pdf_f = ROOT / "results" / "figures" / f["file"]
            if pdf_f.exists() and (ROOT / f["source"]).exists():
                shutil.copy2(pdf_f, st / "figures" / f["file"])
        for src, dst, pat in (
            ("results/summary", "summaries", "*.json"),
            ("paper/tables", "tables", "*.tex"),
        ):
            (st / dst).mkdir()
            for f in sorted((ROOT / src).glob(pat)):
                shutil.copy2(f, st / dst / f.name)
        pdf = ROOT / "paper" / "main.pdf"
        if pdf.exists():
            shutil.copy2(pdf, st / "paper.pdf")
        (st / "README.md").write_text(
            "# Supplementary material\n\n"
            f"Artifact (anonymous): {a.artifact_url}\n\n"
            "- `console/`: the results Console, read-only. Serve it with "
            "`python3 -m http.server -d console 8040` and open http://localhost:8040.\n"
            "- `summaries/`: every per-cell summary the paper's numbers and figures come from.\n"
            "- `figures/`, `tables/`: as in the paper, rebuilt from `summaries/`.\n"
            f"\nBuilt {time.strftime('%Y-%m-%d')}.\n"
        )
        chk = subprocess.run(
            [PY, "scripts/v2/45_anon_check.py", "--root", str(st), "--repo-strict"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if chk.returncode:
            print(chk.stdout)
            sys.exit("the staged supplement names the authors; nothing written")
        out = ROOT / "results" / "final"
        out.mkdir(parents=True, exist_ok=True)
        z = shutil.make_archive(
            str(out / "supplementary"), "zip", root_dir=tmp, base_dir="supplementary"
        )
        mb = Path(z).stat().st_size / 1e6
        n = sum(1 for p in st.rglob("*") if p.is_file())
        print(f"{n} files, {mb:.1f} MB -> {Path(z).relative_to(ROOT)} (anonymity check passed)")
        if mb > a.max_mb:
            sys.exit(f"over the {a.max_mb:g} MB limit")


if __name__ == "__main__":
    main()
