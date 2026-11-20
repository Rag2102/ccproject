"""Morris elementary-effects screening (Morris 1991; Campolongo et al. 2007), in-repo (owner, 5 Oct
2026: no SALib dependency). Plan Week 20, global sensitivity.

Each of r trajectories starts at a random point of a p-level grid on [0, 1]^k and moves one factor
at a time by +/- delta = p / (2 (p - 1)), in a random order, so a trajectory costs k + 1 model
runs. The elementary effect of factor i is the change in the output divided by delta. Summaries
per factor: mu* (mean absolute effect, the influence ranking), mu (mean, with sign) and sigma (SD:
non-linearity or interaction).
"""

from __future__ import annotations

import numpy as np


def trajectories(k: int, r: int, p: int = 4, seed: int = 0) -> np.ndarray:
    """(r, k + 1, k) points in [0, 1]^k."""
    rng = np.random.default_rng(seed)
    delta = p / (2 * (p - 1))
    levels = np.arange(p) / (p - 1)
    base_levels = levels[levels <= 1 - delta + 1e-12]
    out = np.empty((r, k + 1, k))
    for t in range(r):
        x = rng.choice(base_levels, size=k)
        signs = rng.choice([-1.0, 1.0], size=k)
        # a factor that would leave [0, 1] moving up starts high and moves down instead
        start = np.where(signs > 0, x, x + delta)
        order = rng.permutation(k)
        pts = [start.copy()]
        cur = start.copy()
        for i in order:
            cur = cur.copy()
            cur[i] += signs[i] * delta
            pts.append(cur)
        out[t] = np.array(pts)
    return np.clip(out, 0.0, 1.0)


def effects(traj: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Elementary effects (r, k) from trajectory points and outputs y of shape (r, k + 1)."""
    r, n, k = traj.shape
    ee = np.empty((r, k))
    for t in range(r):
        dx = np.diff(traj[t], axis=0)  # one non-zero entry per step
        dy = np.diff(y[t])
        i = np.argmax(np.abs(dx), axis=1)
        ee[t, i] = dy / dx[np.arange(k), i]
    return ee


def summarise(ee: np.ndarray, names: list[str]) -> list[dict]:
    rows = [
        {
            "factor": n,
            "mu_star": float(np.mean(np.abs(ee[:, i]))),
            "mu": float(np.mean(ee[:, i])),
            "sigma": float(np.std(ee[:, i], ddof=1)) if len(ee) > 1 else 0.0,
        }
        for i, n in enumerate(names)
    ]
    rows.sort(key=lambda r: r["mu_star"], reverse=True)
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    return rows


def scale(u: np.ndarray, lo: float, hi: float, log: bool = False) -> np.ndarray:
    """Map [0, 1] to [lo, hi], linearly or on a log scale."""
    if log:
        return np.exp(np.log(lo) + u * (np.log(hi) - np.log(lo)))
    return lo + u * (hi - lo)
