#!/bin/zsh
# Week 21, task 2: seed replication of the confirmatory cells (A3, A5, B1, B2, C x 1%, 2%; P2, P4-P6,
# plus P0 for benefit captured) on replication seeds 1001-1030, reusing the dev-seed P2 tuning.
# It tests luck, not simulator misspecification. Resumable. Logs in logs/w21/.
cd ~/Desktop/ccproject
mkdir -p logs/w21
SEL=(--regimes A3 A5 B1 B2 C --policies P0 P2 P4 P5 P6 --budgets 1 2)
echo "start $(date +%T) $(git rev-parse --short HEAD)"
for i in 1 2 3 4 5 6 7 8; do
  .venv/bin/python scripts/v2/24_run_matrix.py --phase run --groups A B C $SEL --seeds 1001-1030 --family replication --shard $i/8 > logs/w21/run_$i.log 2>&1 &
done
wait
.venv/bin/python scripts/v2/24_run_matrix.py --phase collect --groups A B C $SEL --seeds 1001-1030 --subdir replication > logs/w21/collect.log 2>&1
.venv/bin/python scripts/v2/30_stats.py --groups A B C --subdir replication > logs/w21/stats.log 2>&1
echo "done $(date +%T)"
