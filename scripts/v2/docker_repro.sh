#!/bin/zsh
# Week 24, task 3: reproduce one table (small Table 3) from scratch in a clean container and
# compare it with the copy produced on this machine. Needs Docker running.
set -e
cd "$(dirname $0)/../.."
REF=${1:-HEAD}
CTX=$(mktemp -d)
git archive --format=tar "$REF" | tar -x -C "$CTX"
docker build --build-arg GIT_SHA=$(git rev-parse "$REF") -t vmmbench-repro:$(git rev-parse --short "$REF") "$CTX"
OUT=$(mktemp -d)
docker run --rm -v "$OUT":/out vmmbench-repro:$(git rev-parse --short "$REF") \
  sh -c 'PY=python sh scripts/v2/reproduce_small.sh && cp -r results/small/summary /out/'
.venv/bin/python scripts/v2/compare_tables.py results/small/summary/table3.csv "$OUT/summary/table3.csv"
echo "container output: $OUT/summary"
