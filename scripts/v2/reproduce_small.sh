#!/bin/sh
# Week 21/25: reduced versions of every main figure and table (300 hosts, seeds 1-3); minutes on a
# laptop. Used by `make reproduce-small` and by the clean-container check (Dockerfile). POSIX sh, so
# it runs in a slim image without make. PY defaults to the project venv.
set -e
cd "$(dirname "$0")/../.."
PY=${PY:-.venv/bin/python}
G="A E B C D"
$PY scripts/v2/24_run_matrix.py --small --phase tune --groups $G
$PY scripts/v2/24_run_matrix.py --small --phase run --groups $G --seeds 1-3
$PY scripts/v2/24_run_matrix.py --small --phase collect --groups $G --seeds 1-3
$PY scripts/v2/30_stats.py --small --groups $G
$PY scripts/v2/34_vs_p0.py --small
$PY scripts/v2/31_fig_f4.py --small
$PY scripts/v2/27_pareto.py --small
$PY scripts/v2/28_table3.py --small
$PY scripts/v2/33_adaptive.py --small
echo "figures in results/small/figures, summaries in results/small/summary"
