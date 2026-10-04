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
AZURE = ROOT / "data" / "processed" / "azure_vms_clean.csv.gz"
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


@lru_cache(maxsize=1)
def azure_table() -> pd.DataFrame:
    cols = ["memory_gb", "vcores", "avg_cpu", "criticality_weight", "lifetime_s"]
    t = pd.read_csv(AZURE, usecols=cols)
    t["tier"] = t["criticality_weight"].round(1).map(TIER_OF_WEIGHT).astype(np.int8)
    return t.drop(columns="criticality_weight")


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
