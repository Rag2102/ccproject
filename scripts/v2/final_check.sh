#!/bin/zsh
# Week 39, task 2: the final numbers check. Clone the repository at a revision (default: the
# results-frozen tag if it exists, else HEAD) into a scratch directory, rebuild every summary
# and number from the committed cell Parquets, and require the rebuilt files to equal the
# committed ones byte for byte. Then the tests, the reporting audit, the bibliography check and,
# when LaTeX is installed, the PDF build with a check that every font is embedded.
#   scripts/v2/final_check.sh            # or: scripts/v2/final_check.sh <rev>
set -e
SRC=~/Desktop/ccproject
REV=${1:-$(git -C $SRC rev-parse -q --verify results-frozen >/dev/null && echo results-frozen || echo HEAD)}
T=$(mktemp -d)
trap 'rm -rf $T' EXIT
git clone -q $SRC $T/repo
cd $T/repo
git checkout -q $REV
ln -s $SRC/.venv .venv
echo "== clean clone of $(git rev-parse --short HEAD) ($REV) in $T"

GROUPS=($(for g in A B C D E; do [[ -n $(print -l results/raw/$g/*.parquet(N)) ]] && echo $g; done))
echo "== statistics from the committed cells (groups: $GROUPS)"
.venv/bin/python scripts/v2/30_stats.py --groups $GROUPS > /dev/null
.venv/bin/python scripts/v2/34_vs_p0.py --groups $GROUPS > /dev/null
[[ " $GROUPS " == *" D "* ]] && .venv/bin/python scripts/v2/33_adaptive.py > /dev/null
.venv/bin/python scripts/v2/37_explore_avoid.py --summary-only > /dev/null
.venv/bin/python scripts/v2/40_numbers.py
CHANGED=$(git status --porcelain -- results/summary paper/numbers.tex)
if [[ -n $CHANGED ]]; then
  echo "FAIL rebuilt files differ from the committed ones:"; echo $CHANGED
  git --no-pager diff --stat -- results/summary paper/numbers.tex
  exit 1
fi
echo "ok   summaries and numbers.tex rebuild identically"

echo "== tests, reporting audit, bibliography"
.venv/bin/python -m pytest tests -q 2>&1 | tail -1
.venv/bin/python scripts/v2/43_report_audit.py | tail -1
.venv/bin/python scripts/v2/46_refs_check.py | tail -1

if command -v latexmk >/dev/null; then
  echo "== PDF"
  (cd paper && latexmk -pdf -interaction=nonstopmode -quiet main.tex > /dev/null)
  if pdffonts paper/main.pdf | awk 'NR > 2 && $(NF-4) != "yes" {bad = 1} END {exit bad}'; then
    echo "ok   every font embedded"
  else
    echo "FAIL fonts not embedded:"; pdffonts paper/main.pdf; exit 1
  fi
  mkdir -p $SRC/results/final && cp paper/main.pdf $SRC/results/final/main_$(git rev-parse --short HEAD).pdf
  echo "ok   archived results/final/main_$(git rev-parse --short HEAD).pdf"
else
  echo "note LaTeX not installed: PDF build and font check skipped"
fi
echo "final check passed for $REV"
