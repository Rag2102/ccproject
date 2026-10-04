# v1 final state (frozen 4 Oct 2026)

This file records exactly what v1 was when v2 started. The frozen copies are in `v1_reference/` (read-only, checksums in `v1_reference/MANIFEST.sha256`). The Week 13 regression reads only from there.

## Identity

| Item | Value |
| --- | --- |
| Repository | `git@github.com:Rag2102/ccproject.git`, branch `main` |
| Commit | `729fb7511f2d001c56a1bbd9b525cf76d36cc4f3` (31 Aug 2026, "Add input validation, CloudFront+WAF for API, CI scanning, IAM tightening, observability, load test, OpenAPI spec") |
| Commits on main | 10 |
| Tags | none on the remote before this file; `v1.0-course` is created in Week 1 |
| Python used for the checks below | 3.12.14 (macOS, venv from `requirements.txt` + `requirements-dev.txt`) |
| Python pins | `.python-version` says 3.11.15, `ci.yml` and the Lambda image use 3.12. v2 uses 3.12 (see docs/v2/decisions/ADR-004-python-3.12.md) |
| Package pins | `v1_reference/pip_freeze_py312.txt` |

## Checks run on 4 Oct 2026

| Check | Command | Result |
| --- | --- | --- |
| Unit tests | `pytest tests/ -q` | 42 passed in 24.9 s |
| Gradient check | `python scripts/test_gqat_numpy_gradcheck.py` | PASS, worst max-relative error 0.000000 |
| Totals from the saved per-host file | sum of `cost_*` columns in `simulation_results_per_host.csv` | cost-sensitive 456,532.7; threshold 410,866.9; threshold matched 442,700.7 |

Note: a bare `pytest -q` at the repository root fails, because it collects `scripts/test_gqat_numpy_gradcheck.py`, which calls `sys.exit` on import. Use `pytest tests/` (as CI does).

## Reference numbers (the Week 3 and Week 13 regression targets)

| Quantity | v1 value | Source file |
| --- | --- | --- |
| Hosts / real failures | 122,618 / 6,912 | `simulation_results_per_host.csv` |
| Mean VMs per host | 16.42 | same |
| Cost, cost-sensitive (5,116 migrations) | 456,533 customer-min | same |
| Cost, threshold tau = 0.0073 (7,980 migrations) | 410,867 | same |
| Cost, threshold matched budget (5,522 migrations) | 442,701 | same |
| Advantage at matched budget, rho = 0 | -3.1% | `docs/task8_summary.md` |
| rho sweep, achieved rho -> advantage | -0.00 -> -3.1%, 0.31 -> +0.3%, 0.73 -> +2.0%, 0.86 -> +3.4% | `correlated_assignment_sweep.csv` |
| Hazard model (HistGBM) | ROC-AUC 0.781, PR-AUC 0.020, Brier 0.00202 | `docs/task3_summary.md` |
| Concordance index (Monte Carlo) | 0.7145 | `docs/task4_summary.md` |
| Migration cost constants | 1,250 MB/s link, 150 MB/s dirty rate at 100% CPU, 60 s fallback, 10 min failure recovery; 100% of VMs converge | `docs/task5_summary.md` |
| GQAT-Net-inspired vs HistGBM (100,000-row sample) | calibrated ROC-AUC 0.7715 / Brier 0.0669 vs 0.7902 / 0.0021 | `gqat_net_vs_histgbm_comparison.csv` |

Regression tolerance: the sweep re-draws VM placement with its own random stream. At rho = 0 it gives 452,735 vs 439,045 (5,076 cost-sensitive migrations), so absolute costs differ from the Task 8 totals by about 0.8% while the percentage matches to 0.1 point. Set the Week 13 tolerance on the percentage.

## Large files (Git LFS, not copied)

SHA-256 of the three LFS objects is in `v1_reference/LFS_OIDS_sha256.txt`: `azure_vms_clean.csv.gz`, `azure_vms_with_costs.csv.gz`, `vmtable.csv.gz`. `backblaze_drives_clean.csv` (8 MB) is regenerable by `scripts/01_preprocess.py` and not copied.

## Known inconsistencies in v1 (do not silently fix; cite this list)

1. `docs/data_summary.md` says 122,619 drives and 6,913 failures; every later document and the per-host file say 122,618 and 6,912. The per-host file is authoritative. Week 4's check allows rounding.
2. `docs/project_scope.md` names Azure Public Dataset V2 (about 2.7M VMs); the data actually used is V1 (2,013,767 VMs).
3. The Backblaze table is a third-party summary (vfonov/hdd_survival_backblaze) with no licence file; Week 4 replaces it with Backblaze's own quarterly files after reading their terms.
4. Task 5's "failure cost is 600x migration cost" check is tautological (both sides share the criticality weight), as `docs/task5_summary.md` already says.
5. Policies are compared at matched migration count, not matched GB of memory moved (v3 audit finding A1).
6. Single seed (42) everywhere in the simulation scripts; no confidence intervals.

## What v1 contains beyond the research pipeline

Flask demo (`webapp/`), AWS serverless deployment (`cloud/`, Terraform, Step Functions fan-out of rho x seed trials), OpenAPI spec, observability notes, load test, Kaplan-Meier baseline (`scripts/09`), permutation importance (`scripts/10`), NumPy GQAT-Net (`scripts/08`, `numpy_nn.py`, `gqat_net_numpy.py`). These stay in place and are off the v2 critical path (ADR-001).
