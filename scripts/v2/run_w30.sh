#!/bin/zsh
# Weeks 29-30 (ADR-009, exploratory): the published migration-cost range. Needs the settings in
# configs/v2/cost_range.yaml (scripts/v2/38_cost_range.py, at least four sources extracted).
# Order (plan W30): derive, check on dev seeds 101-110, and only then the eval seeds: B1, B2 and C
# at G0-low and G0-high, P0 P2 P4 P6 at 1% and 2%, seeds 1-30, as group S (subdir costrange);
# then statistics, the saving against never migrating, and Table 3's exploratory rows.
# About 2 h on 8 cores.
set -e
cd ~/Desktop/ccproject
mkdir -p logs/w30
.venv/bin/python scripts/v2/38_cost_range.py > logs/w30/derive.log 2>&1
CELLS=(B1@G0-low B1@G0-high B2@G0-low B2@G0-high C@G0-low C@G0-high)
.venv/bin/python scripts/v2/39_dev_precheck.py $CELLS --budget 2 > logs/w30/precheck.log 2>&1 || {
  echo "dev-seed pre-check failed: logs/w30/precheck.log"; exit 1; }
SEL=(--extra-regimes $CELLS --groups S --policies P0 P2 P4 P6 --budgets 1 2)
for i in 1 2 3 4 5 6 7 8; do
  .venv/bin/python scripts/v2/24_run_matrix.py --phase tune $SEL --shard $i/8 > logs/w30/tune_$i.log 2>&1 &
done
wait
for i in 1 2 3 4 5 6 7 8; do
  .venv/bin/python scripts/v2/24_run_matrix.py --phase run $SEL --seeds 1-30 --shard $i/8 > logs/w30/run_$i.log 2>&1 &
done
wait
.venv/bin/python scripts/v2/24_run_matrix.py --phase collect $SEL --seeds 1-30 --subdir costrange > logs/w30/collect.log 2>&1
.venv/bin/python scripts/v2/30_stats.py --groups S --subdir costrange > logs/w30/stats.log 2>&1
.venv/bin/python scripts/v2/34_vs_p0.py --groups S --subdir costrange > logs/w30/vs_p0.log 2>&1
.venv/bin/python scripts/v2/28_table3.py > logs/w30/table3.log 2>&1
echo "cost range done $(date +%T)" > logs/w30/done.txt
