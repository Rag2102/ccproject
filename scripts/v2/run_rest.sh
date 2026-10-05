#!/bin/zsh
# Everything after Week 18, in order: Week 19 (B, C, D), Week 20, the Week 21 seed replication and
# the second placement source (B1-f), then the ADR-007 SD extension (A3 and A5 to n = 50; triggered by
# the Week 18 run: SD of Delta above 1.6% for P5 and P6). About 9.5 hours on 8 cores. Resumable: rerun it after a stop
# and finished work is skipped. Then the clean-container check (Week 24, about 25 min on 1 core).
cd ~/Desktop/ccproject
mkdir -p logs/w19 logs/w20 logs/w21
scripts/v2/run_w19.sh > logs/w19/driver.log 2>&1
scripts/v2/run_w20.sh > logs/w20/driver.log 2>&1
scripts/v2/run_w21.sh > logs/w21/driver.log 2>&1
scripts/v2/run_w21_second.sh > logs/w21/driver_second.log 2>&1
# ADR-007 extension: seeds 31-50 for every policy in A3 and A5; collected after Week 19's collect
# (which re-collects group A at 30 seeds), so the 50-seed cells are the ones left on disk
mkdir -p logs/w18x
EXT=(--groups A --regimes A3 A5)
for i in 1 2 3 4 5 6 7 8; do
  .venv/bin/python scripts/v2/24_run_matrix.py --phase run $EXT --seeds 31-50 --shard $i/8 > logs/w18x/run_$i.log 2>&1 &
done
wait
.venv/bin/python scripts/v2/24_run_matrix.py --phase collect $EXT --seeds 1-50 > logs/w18x/collect.log 2>&1
echo "runs done $(date)" > logs/rest_done.txt
if docker info >/dev/null 2>&1; then
  scripts/v2/docker_repro.sh > logs/docker_repro.log 2>&1
fi
echo "all done $(date)" >> logs/rest_done.txt
