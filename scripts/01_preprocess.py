"""
Task 2 — Data acquisition & preprocessing
Cleans the two real datasets used in this project:
  1. Azure Public Dataset V1 vmtable  -> workload criticality + migration-cost proxy
  2. Backblaze-derived HDD survival table -> failure ground truth + time-to-failure

Outputs land in data/processed/. Run from the project root:
    python3 scripts/01_preprocess.py
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)

TRACE_LENGTH_S = 30 * 24 * 3600  # Azure V1 trace spans 30 days, timestamps in seconds from trace start

# ---------------------------------------------------------------------------
# 1. Azure Public Dataset V1 — vmtable (workload criticality + migration cost)
# ---------------------------------------------------------------------------
print("=" * 70)
print("AZURE VMTABLE")
print("=" * 70)

vm_cols = [
    "vm_id", "subscription_id", "deployment_id",
    "ts_created_s", "ts_deleted_s",
    "max_cpu", "avg_cpu", "p95_max_cpu",
    "vm_category", "vcores", "memory_gb",
]
vm = pd.read_csv(RAW / "azure" / "vmtable.csv.gz", header=None, names=vm_cols, compression="gzip")
print(f"Loaded {len(vm):,} VM rows, columns: {list(vm.columns)}")
print("Missing values per column:\n", vm.isna().sum())

# Lifetime + censoring flags. created==0 means the VM already existed when the
# 30-day trace window opened (left-censored); deleted at/after the trace end
# means the VM was still running when the trace closed (right-censored).
vm["lifetime_s"] = vm["ts_deleted_s"] - vm["ts_created_s"]
vm["left_censored"] = vm["ts_created_s"] <= 0
vm["right_censored"] = vm["ts_deleted_s"] >= TRACE_LENGTH_S - 300  # within one 5-min bucket of trace end

# Workload criticality tier, derived from Azure's own VM category label.
# Interactive  -> user/customer-facing, most sensitive to interruption
# Unknown      -> importance not declared, treated as medium/conservative default
# Delay-insensitive -> batch/background, most tolerant of interruption
CRITICALITY_MAP = {
    "Interactive": ("high", 1.0),
    "Unkown": ("medium", 0.6),        # note: source data spells it "Unkown"
    "Unknown": ("medium", 0.6),
    "Delay-insensitive": ("low", 0.3),
}
vm["criticality_tier"] = vm["vm_category"].map(lambda c: CRITICALITY_MAP.get(c, ("medium", 0.6))[0])
vm["criticality_weight"] = vm["vm_category"].map(lambda c: CRITICALITY_MAP.get(c, ("medium", 0.6))[1])

# Migration-cost proxy: live-migration time/downtime scales mainly with memory
# footprint (dirty-page copy) and secondarily with vCPU count (dirty-page rate).
# Coefficients are illustrative Azure-scale placeholders, tuned in task 6.
vm["migration_cost_proxy"] = 0.8 * vm["memory_gb"] + 0.2 * vm["vcores"]

def size_tier(row):
    if row["vcores"] <= 2:
        return "small"
    elif row["vcores"] <= 8:
        return "medium"
    elif row["vcores"] <= 16:
        return "large"
    return "xlarge"

vm["size_tier"] = vm.apply(size_tier, axis=1)

print("\nVM category distribution:\n", vm["vm_category"].value_counts())
print("\nCriticality tier distribution:\n", vm["criticality_tier"].value_counts())
print("\nSize tier distribution:\n", vm["size_tier"].value_counts())
print("\nMigration cost proxy stats:\n", vm["migration_cost_proxy"].describe())
print(f"\nLeft-censored (already running at trace start): {vm['left_censored'].sum():,}")
print(f"Right-censored (still running at trace end):    {vm['right_censored'].sum():,}")

out_cols = [
    "vm_id", "subscription_id", "deployment_id",
    "ts_created_s", "ts_deleted_s", "lifetime_s", "left_censored", "right_censored",
    "max_cpu", "avg_cpu", "p95_max_cpu",
    "vm_category", "criticality_tier", "criticality_weight",
    "vcores", "memory_gb", "migration_cost_proxy", "size_tier",
]
vm[out_cols].to_csv(PROCESSED / "azure_vms_clean.csv.gz", index=False, compression="gzip")
print(f"\nSaved -> data/processed/azure_vms_clean.csv.gz ({len(vm):,} rows)")

# ---------------------------------------------------------------------------
# 2. Backblaze-derived HDD survival table (failure probability + TTF ground truth)
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("BACKBLAZE HDD SURVIVAL")
print("=" * 70)

hdd = pd.read_csv(RAW / "backblaze" / "backblaze_2013_2017_hdd_survival.csv")
print(f"Loaded {len(hdd):,} drive rows, columns: {list(hdd.columns)}")
print("Missing values per column:\n", hdd.isna().sum())

hdd["make"] = hdd["make"].fillna("").replace("", "UNKNOWN")
hdd = hdd.rename(columns={"status": "failed", "capacity": "capacity_tb"})
hdd["failed"] = hdd["failed"].astype(int)

failure_rate = hdd["failed"].mean()
print(f"\nOverall failure rate: {failure_rate:.4%}  ({hdd['failed'].sum():,} failures / {len(hdd):,} drives)")

# Sanity check the core premise: does failure risk actually vary with age?
# (If it didn't, TTF would carry no information and the project's premise
# that TTF-awareness beats a flat threshold would be weaker.)
bins = [0, 90, 365, 730, 1095, 1460, 1825, np.inf]
labels = ["<90d", "90-365d", "1-2y", "2-3y", "3-4y", "4-5y", "5y+"]
hdd["age_bucket"] = pd.cut(hdd["age_days"], bins=bins, labels=labels)
age_table = hdd.groupby("age_bucket", observed=True).agg(
    n_drives=("failed", "size"), n_failed=("failed", "sum")
)
age_table["failure_rate"] = age_table["n_failed"] / age_table["n_drives"]
print("\nFailure rate by age bucket (sanity check for TTF signal):\n", age_table)

model_table = hdd.groupby("model", observed=True).agg(
    n_drives=("failed", "size"), n_failed=("failed", "sum")
)
model_table["failure_rate"] = model_table["n_failed"] / model_table["n_drives"]
model_table = model_table[model_table["n_drives"] >= 500].sort_values("failure_rate", ascending=False)
print("\nTop-10 highest failure-rate models (>=500 drives):\n", model_table.head(10))

hdd.to_csv(PROCESSED / "backblaze_drives_clean.csv", index=False)
age_table.to_csv(PROCESSED / "backblaze_failure_rate_by_age.csv")
model_table.to_csv(PROCESSED / "backblaze_failure_rate_by_model.csv")
print(f"\nSaved -> data/processed/backblaze_drives_clean.csv ({len(hdd):,} rows)")
print("Saved -> data/processed/backblaze_failure_rate_by_age.csv")
print("Saved -> data/processed/backblaze_failure_rate_by_model.csv")

print("\nDone.")
