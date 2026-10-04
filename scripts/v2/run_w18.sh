#!/bin/zsh
# Week 18: tune P2, run A1-A7 and E1-E3 on eval seeds 1-30 (8 shards), collect. Resumable:
# rerunning skips finished tuning files and records. Logs in logs/w18/.
cd ~/Desktop/ccproject
echo "start $(date +%T) $(git rev-parse --short HEAD)"
for i in 1 2 3 4 5 6 7 8; do
  .venv/bin/python scripts/v2/24_run_matrix.py --phase tune --groups A E --shard $i/8 > logs/w18/tune_$i.log 2>&1 &
done
wait
echo "tune done $(date +%T)"
for i in 1 2 3 4 5 6 7 8; do
  .venv/bin/python scripts/v2/24_run_matrix.py --phase run --groups A E --seeds 1-30 --shard $i/8 > logs/w18/run_$i.log 2>&1 &
done
wait
echo "run done $(date +%T)"
.venv/bin/python scripts/v2/24_run_matrix.py --phase collect --groups A E --seeds 1-30 > logs/w18/collect.log 2>&1
echo "collect done $(date +%T)"
