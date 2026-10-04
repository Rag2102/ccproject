# v1 anomaly: why the threshold won at rho = 0 (Week 3)

Status: section 1 done (4 Oct 2026); hypotheses H1-H8 and their verdicts to follow (Week 3 tasks 2-3).

## 1. Reproduction from the tag

The number reproduces exactly. Re-running v1 from tag `v1.0-course` gives the same matched-budget comparison as the frozen results.

| Quantity | Re-run | v1_reference |
| --- | --- | --- |
| Cost, cost-sensitive (5,116 migrations) | 456,532.7 | 456,532.7 |
| Cost, threshold at matched budget (tau = 0.01468, 5,522 migrations) | 442,700.7 | 442,700.7 |
| Gap | cost-sensitive 3.1% higher | 3.1% |
| Missed failures, cost-sensitive vs matched threshold | 5,493 vs 5,311 | same |
| Cost, naive threshold (tau = 0.00731, 7,980 migrations) | 410,866.9 | 410,866.9 |

How it was checked:

- Worktree at the tag: `git worktree add ../ccproject-v1 v1.0-course` (so the run cannot overwrite files on `v2-research`), then `python scripts/06_simulation_evaluation.py` from `scripts/`, with the pinned environment (Python 3.12.14, `v1_reference/pip_freeze_py312.txt`). Run time 11 s.
- `simulation_headline_summary.csv`: byte-identical to `v1_reference` (same SHA-256).
- `simulation_results_per_host.csv`: same shape (122,618 x 23), same columns, every text column (all four outcome labels per host) identical; numeric columns differ by at most 8.9e-16, i.e. last-bit floating-point noise. The file hash therefore differs; the results do not.
- Inputs: 122,618 hosts, 6,912 failures, 2,013,767 VMs, 16.4 VMs per host, seed 42.

Consequence for Week 13: the v1 regression check (G2, within 1%) can compare against `v1_reference` directly; a tolerance far tighter than 1% is achievable for v1 itself.
