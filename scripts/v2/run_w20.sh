#!/bin/zsh
# Week 20: ablations, P2 retuning and robustness grid, Morris screening, failure-analysis runs
# (8 shards each), then collect. Needs the Week 18-19 P2 tuning files. Resumable. Logs in logs/w20/.
cd ~/Desktop/ccproject
mkdir -p logs/w20
echo "start $(date +%T) $(git rev-parse --short HEAD)"
for phase in ablate rtune robust morris failure; do
  for i in 1 2 3 4 5 6 7 8; do
    .venv/bin/python scripts/v2/26_run_w20.py --phase $phase --shard $i/8 > logs/w20/${phase}_$i.log 2>&1 &
  done
  wait
  echo "$phase done $(date +%T)"
done
.venv/bin/python scripts/v2/26_run_w20.py --phase collect > logs/w20/collect.log 2>&1
echo "collect done $(date +%T)"
