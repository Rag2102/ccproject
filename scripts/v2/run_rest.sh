#!/bin/zsh
# Everything after Week 18, in order: Week 19 (B, C, D), Week 20, the Week 21 seed replication and
# the second placement source (B1-f). About 9 hours on 8 cores. Resumable: rerun it after a stop
# and finished work is skipped. Then the clean-container check (Week 24, about 25 min on 1 core).
cd ~/Desktop/ccproject
mkdir -p logs/w19 logs/w20 logs/w21
scripts/v2/run_w19.sh > logs/w19/driver.log 2>&1
scripts/v2/run_w20.sh > logs/w20/driver.log 2>&1
scripts/v2/run_w21.sh > logs/w21/driver.log 2>&1
scripts/v2/run_w21_second.sh > logs/w21/driver_second.log 2>&1
echo "runs done $(date)" > logs/rest_done.txt
if docker info >/dev/null 2>&1; then
  scripts/v2/docker_repro.sh > logs/docker_repro.log 2>&1
fi
echo "all done $(date)" >> logs/rest_done.txt
