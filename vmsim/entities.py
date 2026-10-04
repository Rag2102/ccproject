"""Hosts, drives and VMs as structures of arrays (SIM_SPEC section 3).

VM attributes are resampled jointly from the Azure V1 trace (size, CPU, tier and lifetime come
from the same VM), drives from the Backblaze drive table. Only static attributes live here; the
event engine (Week 13) owns the mutable state.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AZURE = ROOT / "data" / "processed" / "azure_vms_clean.csv.gz"  # Git LFS
AZURE_EXTRACT = ROOT / "data" / "processed" / "azure_vms_vmsim.parquet"  # committed
V1_DRIVES = ROOT / "data" / "processed" / "backblaze_drives_clean.csv"
TIER_OF_WEIGHT = {0.3: 0, 0.6: 1, 1.0: 2}  # v1: low, medium, high


@dataclass(frozen=True)
class VMs:
    mem_gb: np.ndarray
    vcores: np.ndarray
    avg_cpu: np.ndarray
    tier: np.ndarray  # 0 low, 1 medium, 2 high
    lifetime_s: np.ndarray
    source_row: np.ndarray  # row in the Azure table, for traceability

    def __len__(self) -> int:
        return len(self.mem_gb)


@dataclass(frozen=True)
class Hosts:
    cap_gb: np.ndarray
    drives: np.ndarray  # (n_hosts, drives_per_host) indices into the drive table
    rack: np.ndarray

    def __len__(self) -> int:
        return len(self.cap_gb)


def azure_table_from_csv() -> pd.DataFrame:
    cols = ["memory_gb", "vcores", "avg_cpu", "criticality_weight", "lifetime_s"]
    t = pd.read_csv(AZURE, usecols=cols)
    t["tier"] = t["criticality_weight"].round(1).map(TIER_OF_WEIGHT).astype(np.int8)
    return t.drop(columns="criticality_weight")


@lru_cache(maxsize=1)
def azure_table() -> pd.DataFrame:
    """The Azure VM columns vmsim uses. Read from the committed extract (exact copy of these
    columns, scripts/v2/09_azure_extract.py), so a checkout without Git LFS works; the LFS CSV is
    the fallback."""
    if AZURE_EXTRACT.exists():
        return pd.read_parquet(AZURE_EXTRACT)
    return azure_table_from_csv()


@lru_cache(maxsize=1)
def v1_drive_table() -> pd.DataFrame:
    return pd.read_csv(V1_DRIVES).dropna(subset=["age_days"]).reset_index(drop=True)


def sample_vms(n: int, rng: np.random.Generator) -> VMs:
    t = azure_table()
    rows = rng.integers(0, len(t), n)
    s = t.iloc[rows]
    return VMs(
        mem_gb=s["memory_gb"].to_numpy(float),
        vcores=s["vcores"].to_numpy(float),
        avg_cpu=s["avg_cpu"].to_numpy(float),
        tier=s["tier"].to_numpy(np.int8),
        lifetime_s=s["lifetime_s"].to_numpy(float),
        source_row=rows,
    )


def all_v1_vms() -> VMs:
    """Every VM of the Azure table, in file order (the v1 regression uses all of them)."""
    t = azure_table()
    return VMs(
        mem_gb=t["memory_gb"].to_numpy(float),
        vcores=t["vcores"].to_numpy(float),
        avg_cpu=t["avg_cpu"].to_numpy(float),
        tier=t["tier"].to_numpy(np.int8),
        lifetime_s=t["lifetime_s"].to_numpy(float),
        source_row=np.arange(len(t)),
    )


def make_hosts(
    n: int, drives_per_host: int, cap_gb: float, rng: np.random.Generator, hosts_per_rack: int = 40
) -> Hosts:
    """Hosts with drives drawn without replacement from the drive table (with replacement if
    more slots than drives)."""
    n_drives = len(v1_drive_table())
    need = n * drives_per_host
    idx = rng.choice(n_drives, need, replace=need > n_drives)
    return Hosts(
        cap_gb=np.full(n, float(cap_gb)),
        drives=idx.reshape(n, drives_per_host),
        rack=np.arange(n) // hosts_per_rack,
    )


# --- residents and transients (SIM_SPEC section 3, VM churn) -----------------------------------
# A VM that lives at least a day is a resident and is simulated individually; a shorter one is a
# transient. Transients are 88% of Azure VMs but 8% of memory-time; they are charged at each host
# failure from the failure stream and are never eligible for migration (MIN_MIGRATE_AGE_DAYS),
# so they cost every policy the same.
RESIDENT_MIN_S = 86_400.0
MIN_MIGRATE_AGE_DAYS = 1.0


@lru_cache(maxsize=1)
def split() -> dict:
    t = azure_table()
    life = t["lifetime_s"].to_numpy(float)
    mem = t["memory_gb"].to_numpy(float)
    res = life >= RESIDENT_MIN_S
    mt = mem * life / 86_400
    return {
        "resident_rows": np.flatnonzero(res),
        "transient_rows": np.flatnonzero(~res),
        "resident_mem_share": float(mt[res].sum() / mt.sum()),
        "resident_mem_days_mean": float(mt[res].mean()),  # E[mem x lifetime] per resident, GB-days
        "transients_per_resident": float((~res).sum() / res.sum()),
        "transient_life_mean_days": float(life[~res].mean() / 86_400),
    }


@lru_cache(maxsize=1)
def _lifetimes_sorted() -> np.ndarray:
    return np.sort(azure_table()["lifetime_s"].to_numpy(float) / 86_400)


def survival(age_days: np.ndarray, ahead_days: float) -> np.ndarray:
    """P(lifetime > age + ahead | lifetime > age), from the empirical Azure distribution."""
    s = _lifetimes_sorted()
    n = len(s)
    a = np.asarray(age_days, float)
    alive_now = n - np.searchsorted(s, a, side="right")
    alive_then = n - np.searchsorted(s, a + ahead_days, side="right")
    return np.where(alive_now > 0, alive_then / np.maximum(alive_now, 1), 0.0)


def take(vms: VMs, idx: np.ndarray) -> VMs:
    return VMs(**{k: getattr(vms, k)[idx] for k in vms.__dataclass_fields__})


def rows_to_vms(rows: np.ndarray) -> VMs:
    t = azure_table()
    s = t.iloc[rows]
    return VMs(
        mem_gb=s["memory_gb"].to_numpy(float),
        vcores=s["vcores"].to_numpy(float),
        avg_cpu=s["avg_cpu"].to_numpy(float),
        tier=s["tier"].to_numpy(np.int8),
        lifetime_s=s["lifetime_s"].to_numpy(float),
        source_row=np.asarray(rows),
    )


def sample_present_residents(target_gb: float, rng: np.random.Generator) -> tuple[VMs, np.ndarray]:
    """Residents present at a random instant, filling target_gb: drawn with probability
    proportional to lifetime (length bias) and a uniform elapsed age. Returns (vms, age_days)."""
    sp = split()
    rows = sp["resident_rows"]
    life = azure_table()["lifetime_s"].to_numpy(float)[rows]
    mean_mem = azure_table()["memory_gb"].to_numpy(float)[rows].mean()
    n = int(2 * target_gb / mean_mem) + 10
    pick = rows[rng.choice(len(rows), n, p=life / life.sum())]
    vms = rows_to_vms(pick)
    keep = np.cumsum(vms.mem_gb) <= target_gb
    vms = take(vms, np.flatnonzero(keep))
    age = rng.uniform(size=len(vms)) * vms.lifetime_s / 86_400
    return vms, age
