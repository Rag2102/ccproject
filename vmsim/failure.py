"""Host failure process (plan Week 12; SIM_SPEC section 7).

Daily host hazard = 1 - prod(1 - h_drive) * (1 - h_other), where
  h_drive  comes from a hazard source: "v1_lookup" (v1's 30-day hazard by model group and age,
           until the Week 7 model is plugged in as "model");
  h_other  is a Weibull (shape < 1) whose scale makes non-disk failures `non_disk_multiplier`
           times as likely over a year as disk failures, an explicit, swept assumption.
Failure times are drawn by inverse transform on the cumulative hazard, with constant hazard
within a day, so the time inside the day is exact rather than rounded.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from vmsim.entities import v1_drive_table

ROOT = Path(__file__).resolve().parents[1]
V1_LOOKUP = ROOT / "data" / "processed" / "ttf_lookup_table.csv"
BIN = 30


@lru_cache(maxsize=1)
def v1_lookup() -> tuple[dict[str, int], np.ndarray]:
    """(model group -> row, 30-day hazard per (group, bin)); the last bin extends forever."""
    t = pd.read_csv(V1_LOOKUP).sort_values(["model_grp", "bin_start_days"])
    groups = sorted(t["model_grp"].unique())
    nb = int(t["bin_start_days"].max() // BIN) + 1
    h = np.zeros((len(groups), nb))
    for gi, g in enumerate(groups):
        s = t[t["model_grp"] == g]
        h[gi, (s["bin_start_days"] // BIN).astype(int)] = s["hazard_30d"].to_numpy()
        last = int(s["bin_start_days"].max() // BIN)
        h[gi, last + 1 :] = h[gi, last]
    return {g: i for i, g in enumerate(groups)}, h


def drive_group(drive_idx: np.ndarray) -> np.ndarray:
    groups, _ = v1_lookup()
    model = v1_drive_table()["model"].to_numpy()[drive_idx]
    return np.array([groups.get(m, groups["OTHER"]) for m in model])


def drive_hazard_v1(drive_idx: np.ndarray, age0_days: np.ndarray, n_days: int) -> np.ndarray:
    """Daily hazard of each drive for days 0..n_days-1 of the run (shape drives x days)."""
    _, h30 = v1_lookup()
    g = drive_group(drive_idx.ravel())
    age = age0_days.ravel()[:, None] + np.arange(n_days)[None, :]
    b = np.minimum((age // BIN).astype(int), h30.shape[1] - 1)
    return (1 - (1 - h30[g[:, None], b]) ** (1 / BIN)).reshape(*drive_idx.shape, n_days)


def weibull_daily(age0_days: np.ndarray, n_days: int, shape: float, scale: float) -> np.ndarray:
    a = age0_days[:, None] + np.arange(n_days + 1)[None, :]
    cum = (a / scale) ** shape
    return 1 - np.exp(-np.diff(cum, axis=1))


def weibull_scale_for(p_year: float, shape: float) -> float:
    """Scale such that a new host fails within 365 days with probability p_year."""
    if p_year <= 0:
        return np.inf
    return 365.0 / (-np.log(1 - p_year)) ** (1 / shape)


def host_hazard(
    drives: np.ndarray, age0: np.ndarray, n_days: int, non_disk_multiplier: float, shape: float
) -> tuple[np.ndarray, np.ndarray]:
    """(daily host hazard, daily disk-only host hazard), each hosts x days.

    drives, age0: (hosts, drives_per_host). Host age for the non-disk term is its oldest drive.
    """
    hd = drive_hazard_v1(drives, age0, n_days)
    disk = 1 - np.prod(1 - hd, axis=1)
    if non_disk_multiplier <= 0:
        return disk, disk
    p_disk_year = float(np.mean(1 - np.prod(1 - disk[:, :365], axis=1)))
    scale = weibull_scale_for(min(non_disk_multiplier * p_disk_year, 0.99), shape)
    other = weibull_daily(age0.max(axis=1), n_days, shape, scale)
    return 1 - (1 - disk) * (1 - other), disk


def sample_failure_times(h: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """First failure time of each host in days (inf if none in the matrix); inverse transform."""
    rate = -np.log1p(-np.clip(h, 0, 1 - 1e-15))  # constant hazard within each day
    cum = np.concatenate([np.zeros((len(h), 1)), np.cumsum(rate, axis=1)], axis=1)
    e = rng.exponential(size=len(h))
    day = np.array([np.searchsorted(c, x, side="right") - 1 for c, x in zip(cum, e, strict=True)])
    out = np.full(len(h), np.inf)
    ok = day < h.shape[1]
    d = day[ok]
    out[ok] = d + (e[ok] - cum[ok, d]) / rate[ok, d]
    return out


def initial_ages(drive_idx: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Age of each drive at the start of the run: a uniform point of its observed life in v1."""
    life = v1_drive_table()["age_days"].to_numpy()[drive_idx]
    return np.floor(rng.uniform(size=drive_idx.shape) * life)
