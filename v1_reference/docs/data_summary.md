# Task 2 — Data Acquisition & Preprocessing: Results

## What was pulled (both real, both verified)

| Dataset | Source | Rows | Role in project |
|---|---|---|---|
| Azure Public Dataset V1 — `vmtable` | Microsoft's own released Azure VM trace (github.com/Azure/AzurePublicDataset, official GitHub release asset, 163MB compressed) | 2,013,767 VMs, 30-day trace | Workload criticality (`vm_category`) + migration-cost proxy (vcores, memory) |
| Backblaze HDD survival table (2013–2017) | Derived from Backblaze's own published daily SMART/failure data ([backblaze.com/b2/hard-drive-test-data.html](https://www.backblaze.com/b2/hard-drive-test-data.html)); real per-drive outcomes, summarized by [vfonov/hdd_survival_backblaze](https://github.com/vfonov/hdd_survival_backblaze) | 122,619 drives, 6,913 real failures | Failure probability + time-to-failure (TTF) ground truth |

**Why this combination, and a note on provenance:** the cloud sandbox this project runs in only has network access to package registries and GitHub — not to Backblaze's own B2 storage or Azure's blob storage directly. Azure's vmtable turned out to be hosted as a GitHub release asset, so it downloaded directly and is the untouched original file. Backblaze's raw daily-SMART files (tens of GB, quarterly ZIPs) aren't reachable that way, so this project uses a pre-aggregated survival table built by a third party directly from Backblaze's real 2013–2017 daily files (one row per real drive, with real failure/censored status and real age-at-observation, derived from each drive's actual SMART power-on-hours counter). It is not synthetic — every row is a real drive with a real outcome — but if you'd rather work from Backblaze's original daily CSVs, connecting a folder on your Mac would let me download those directly (your machine isn't behind the same network restriction) and rebuild this step from the raw files. Flagging so it's your call, not a silent substitution.

## What preprocessing produced

`scripts/01_preprocess.py` (run with `python3 scripts/01_preprocess.py` from the project root) reads both raw sources and writes to `data/processed/`:

- **`azure_vms_clean.csv.gz`** (2,013,767 rows) — adds `lifetime_s`, `left_censored`/`right_censored` flags (VM already running when the 30-day window opened / still running when it closed), `criticality_tier` + `criticality_weight` mapped from `vm_category`, `migration_cost_proxy` (weighted on memory footprint + vCPU count, since live-migration cost is dominated by dirty-page memory copy), and a `size_tier` bucket.
- **`backblaze_drives_clean.csv`** (122,619 rows) — cleaned failure/censoring status, capacity, model.
- **`backblaze_failure_rate_by_age.csv`** and **`backblaze_failure_rate_by_model.csv`** — sanity-check tables (see below).

## Key findings from preprocessing (these will shape task 3's model)

**Workload side:** VM category splits 58% Unknown / 39% Delay-insensitive / 3% Interactive — so "high criticality" VMs are a small minority, meaning the cost-sensitive policy's edge over a flat threshold should show up most clearly on that 3% slice. Migration cost proxy ranges 0.8–92.8 (cost units), median 3.2 — a long right tail from a small number of large VMs, which is exactly the case where ignoring cost (as a threshold policy does) is expected to look worst.

**Failure side:** overall failure rate is 5.6%, consistent with published Backblaze annualized failure rates. Failure rate by age is *not* monotonic (541/8145 in the first 90 days, peaking around 1–3 years, then dropping past 5 years) — age alone is a weak, noisy signal. Failure rate by **drive model** is far more informative: `ST3000DM001` fails at 36.3% (this is the well-documented real 2011–2012 Seagate 3TB batch that Backblaze publicly flagged as a bad cohort), versus 3.2% for `HDS5C4040ALE630`, an order of magnitude apart. **Implication for task 3:** the failure-probability and TTF models should condition on drive model, not just age — model identity is the dominant real signal in this data, which is a more realistic (and more defensible) setup than an age-only hazard curve.

## Files in this task

- `scripts/01_preprocess.py` — the preprocessing script (rerunnable, ~1–2 min)
- `data/processed/*.csv(.gz)` — cleaned outputs
- `data/raw/azure/`, `data/raw/backblaze/` — original downloaded files, untouched
