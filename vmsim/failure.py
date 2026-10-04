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


def non_disk_scale(disk: np.ndarray, non_disk_multiplier: float, shape: float) -> float:
    """Weibull scale making a new host's non-disk failures `non_disk_multiplier` times as likely
    over a year as the cluster's mean disk failure probability (disk: hosts x days)."""
    p_disk_year = float(np.mean(1 - np.prod(1 - disk[:, :365], axis=1)))
    return weibull_scale_for(min(non_disk_multiplier * p_disk_year, 0.99), shape)


def host_hazard(
    drives: np.ndarray,
    age0: np.ndarray,
    n_days: int,
    non_disk_multiplier: float,
    shape: float,
    scale: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """(daily host hazard, daily disk-only host hazard), each hosts x days.

    drives, age0: (hosts, drives_per_host). Host age for the non-disk term is its oldest drive.
    scale: the non-disk Weibull scale; by default set from these hosts (non_disk_scale).
    """
    hd = drive_hazard_v1(drives, age0, n_days)
    disk = 1 - np.prod(1 - hd, axis=1)
    if non_disk_multiplier <= 0:
        return disk, disk
    if scale is None:
        scale = non_disk_scale(disk, non_disk_multiplier, shape)
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


def renewal_hazard(world, fc, n_days: int) -> np.ndarray:
    """Daily hazard of each host after a repair, by days since the repair (hosts x days).

    A repaired host gets new drives of the same models at age 0 (SIM_SPEC section 4); the
    non-disk scale is the one of the host's first life, so the multiplier keeps its meaning.
    """
    if fc.non_disk_multiplier <= 0:
        scale = None
    else:
        scale = non_disk_scale(world.disk_hazard, fc.non_disk_multiplier, fc.weibull_shape)
    hz, _ = host_hazard(
        world.drives,
        np.zeros_like(world.age0),
        n_days,
        fc.non_disk_multiplier,
        fc.weibull_shape,
        scale,
    )
    return hz


def first_time(cum: np.ndarray, e: np.ndarray, rate: np.ndarray) -> np.ndarray:
    """Inverse transform for one exponential draw per row: the time where cum crosses e."""
    n = rate.shape[1]
    day = np.array([np.searchsorted(c, x, side="right") - 1 for c, x in zip(cum, e, strict=True)])
    out = np.full(len(e), np.inf)
    ok = day < n
    r = np.flatnonzero(ok)
    d = day[ok]
    out[ok] = d + (e[ok] - cum[r, d]) / rate[r, d]
    return out


def lives(world, fc, n_days: int, streams, new: np.ndarray | None = None) -> np.ndarray:
    """Every failure and repair in [0, n_days), independent of any policy (CRN).

    Returns a structured array sorted by failure time with fields host, life, t_fail, t_repair
    (days from the start of warm-up). Life 0 is the world's first failure; a repaired host draws
    life k from the renewal hazard and its own keyed streams, so every policy sees the same
    schedule.
    """
    if new is None:
        new = renewal_hazard(world, fc, n_days)
    rate = -np.log1p(-np.clip(new, 0, 1 - 1e-15))
    cum = np.concatenate([np.zeros((len(new), 1)), np.cumsum(rate, axis=1)], axis=1)
    rows = []
    t = world.fail_t.astype(float).copy()
    alive = np.flatnonzero(t < n_days)
    k = 0
    while len(alive):
        rep = (
            t[alive]
            + streams.gen("failures", 4, k).lognormal(
                np.log(fc.repair_median_days), fc.repair_sigma, size=len(world.fail_t)
            )[alive]
        )
        rows.append((alive, np.full(len(alive), k), t[alive], rep))
        e = streams.gen("failures", 3, k + 1).exponential(size=len(world.fail_t))[alive]
        start = np.ceil(rep)  # back in service at the next daily tick
        nxt = start + first_time(cum[alive], e, rate[alive])
        t = np.full(len(world.fail_t), np.inf)
        t[alive] = nxt
        alive = alive[nxt < n_days]
        k += 1
    out = np.zeros(
        sum(len(r[0]) for r in rows),
        dtype=[("host", "i8"), ("life", "i8"), ("t_fail", "f8"), ("t_repair", "f8")],
    )
    if rows:
        for f, i in zip(("host", "life", "t_fail", "t_repair"), range(4), strict=True):
            out[f] = np.concatenate([r[i] for r in rows])
    return np.sort(out, order=["t_fail", "host"])
