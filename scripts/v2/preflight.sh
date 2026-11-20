#!/bin/zsh
# Pre-flight for run_rest.sh (about 10 min): the tests, then every queued stage at small scale in a
# throwaway copy of the committed tree, so a crash shows up now and not at hour five. The real
# results/ (including results/small, which the container check compares against) is not touched.
# Exit status 0 only if every stage passed.
set -e
SRC=~/Desktop/ccproject
TMP=$(mktemp -d)/repo
mkdir -p $TMP
git -C $SRC archive HEAD | tar -x -C $TMP
ln -s $SRC/.venv $TMP/.venv
cd $TMP
PY=.venv/bin/python
step() { echo "\n== $1"; }

step "tests"
(cd $SRC && $PY -m pytest tests -q -x 2>&1 | tail -1)

step "reproduce-small (A E B C D; Week 19 small)"
PY=$PY sh scripts/v2/reproduce_small.sh > rs.log 2>&1 && tail -1 rs.log

step "Week 20 (all phases, small)"
$PY scripts/v2/preflight_w20.py 2>&1 | grep -E "preflight|Traceback|Error"

step "Week 21 replication (small)"
SEL=(--regimes A3 A5 B1 B2 C --policies P0 P2 P4 P5 P6 --budgets 1 2)
$PY scripts/v2/24_run_matrix.py --small --phase run --groups A B C $SEL --seeds 1001-1001 --family replication > r.log 2>&1
$PY scripts/v2/24_run_matrix.py --small --phase collect --groups A B C $SEL --seeds 1001-1001 --subdir replication >> r.log 2>&1
$PY scripts/v2/30_stats.py --small --groups A B C --subdir replication 2>&1 | tail -1

step "second source B1-f (small)"
S2=(--extra-regimes B1-f --groups S --policies P0 P2 P4 P5 P6 --budgets 1 2)
$PY scripts/v2/17_calibrate_regimes.py --cells B1-f > s.log 2>&1
$PY scripts/v2/24_run_matrix.py --small --phase tune $S2 >> s.log 2>&1
$PY scripts/v2/24_run_matrix.py --small --phase run $S2 --seeds 1-1 >> s.log 2>&1
$PY scripts/v2/24_run_matrix.py --small --phase collect $S2 --seeds 1-1 --subdir second >> s.log 2>&1
$PY scripts/v2/30_stats.py --small --groups S --subdir second 2>&1 | tail -1

step "ADR-007 extension (small: extra seed, collect over all)"
EXT=(--groups A --regimes A3 A5)
$PY scripts/v2/24_run_matrix.py --small --phase run $EXT --seeds 4-4 > x.log 2>&1
$PY scripts/v2/24_run_matrix.py --small --phase collect $EXT --seeds 1-4 >> x.log 2>&1 && tail -1 x.log

step "ADR-010 avoidance (full scale, A1 and E1, seeds 1-2, joined with the real P0 runs)"
mkdir -p results/raw/A results/raw/E
cp $SRC/results/raw/A/A1_b0_P0.parquet $SRC/results/raw/A/A1_b*_P4.parquet results/raw/A/
cp $SRC/results/raw/E/E1_b0_P0.parquet $SRC/results/raw/E/E1_b*_P4.parquet results/raw/E/
$PY scripts/v2/37_explore_avoid.py --regimes A1 E1 --seeds 1-2 --workers 4 2>&1 | tail -3

step "run scripts parse"
for f in $SRC/scripts/v2/run_w19.sh $SRC/scripts/v2/run_w20.sh $SRC/scripts/v2/run_w21.sh $SRC/scripts/v2/run_w21_second.sh $SRC/scripts/v2/run_rest.sh; do zsh -n $f; done && echo ok

echo "\npreflight passed ($(date +%T)); scratch copy: $TMP"
