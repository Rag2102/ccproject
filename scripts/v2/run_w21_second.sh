#!/bin/zsh
# Week 21, task 3: the second placement source. After `13_trace_rho.py --cell f` and
# `--analyse-second`: calibrate B1-f's arrival blend, tune P2 and run the confirmatory policies
# (P0, P2, P4-P6) at 1% and 2% on eval seeds 1-30 as group S; collect; statistics.
cd ~/Desktop/ccproject
mkdir -p logs/w21
SEL=(--extra-regimes B1-f --groups S --policies P0 P2 P4 P5 P6 --budgets 1 2)
.venv/bin/python scripts/v2/17_calibrate_regimes.py --cells B1-f > logs/w21/calibrate_second.log 2>&1
for i in 1 2 3 4 5 6 7 8; do
  .venv/bin/python scripts/v2/24_run_matrix.py --phase tune $SEL --shard $i/8 > logs/w21/tune_second_$i.log 2>&1 &
done
wait
for i in 1 2 3 4 5 6 7 8; do
  .venv/bin/python scripts/v2/24_run_matrix.py --phase run $SEL --seeds 1-30 --shard $i/8 > logs/w21/run_second_$i.log 2>&1 &
done
wait
.venv/bin/python scripts/v2/24_run_matrix.py --phase collect $SEL --seeds 1-30 --subdir second > logs/w21/collect_second.log 2>&1
.venv/bin/python scripts/v2/30_stats.py --groups S --subdir second > logs/w21/stats_second.log 2>&1
echo "second source done $(date +%T)"
