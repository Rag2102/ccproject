#!/bin/zsh
# Week 19: tune P2, run B1-low, B1, B1-high, B2, C and D on eval seeds 1-30 (8 shards), collect
# all groups. Resumable: rerunning skips finished tuning files and records. Logs in logs/w19/.
cd ~/Desktop/ccproject
mkdir -p logs/w19
echo "start $(date +%T) $(git rev-parse --short HEAD)"
for i in 1 2 3 4 5 6 7 8; do
  .venv/bin/python scripts/v2/24_run_matrix.py --phase tune --groups B C D --shard $i/8 > logs/w19/tune_$i.log 2>&1 &
done
wait
echo "tune done $(date +%T)"
for i in 1 2 3 4 5 6 7 8; do
  .venv/bin/python scripts/v2/24_run_matrix.py --phase run --groups B C D --seeds 1-30 --shard $i/8 > logs/w19/run_$i.log 2>&1 &
done
wait
echo "run done $(date +%T)"
.venv/bin/python scripts/v2/24_run_matrix.py --phase collect --groups A E B C D --seeds 1-30 > logs/w19/collect.log 2>&1
echo "collect done $(date +%T)"
