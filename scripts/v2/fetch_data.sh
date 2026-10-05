#!/bin/zsh
# Week 25: download every third-party input of the v2 study and check it. Not needed for
# `make reproduce-small`, which runs from the committed extracts alone.
#   Backblaze Drive Stats: 45 ZIPs, 35.1 GB (resumable; about 4 h at 20 Mbit/s)
#   Google ClusterData 2019 cells a, b, h (G1) and f (second source): 21.2 + 17.6 + 13.0 + 14.1 GB;
#     every shard is checked against the bucket's MD5 as it arrives; shards are deleted after
#     aggregation unless --keep-raw is passed to 13_trace_rho.py
#   Azure Public Dataset V1: the extract the simulator reads is committed (data/processed)
# Terms of use: docs/v2/data_sources.md. Raw data is never redistributed with this repository.
set -e
cd "$(dirname $0)/../.."
PY=${PY:-.venv/bin/python}
$PY scripts/v2/10_backblaze_ingest.py --all
for cell in a b h f; do
  $PY scripts/v2/13_trace_rho.py --cell $cell
done
$PY scripts/v2/verify_checksums.py
