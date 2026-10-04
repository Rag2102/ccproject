"""Latent Gaussian-copula axis for the A regimes (PROTOCOL section 3; rho_definition.md).

The A regimes are defined by the latent correlation rho_L. The simulator's placement targets the
tie-corrected Spearman between VM tier and host risk (v1's axis, placement.rho_controlled), so
rho_L is converted under the simulator's own margins: the tier shares of resident VMs and a
continuous host risk (n_levels equal-probability levels). Tier shares are those of the VMs
present (lifetime-weighted residents), which is what the engine measures. Same formulas as
scripts/v2/13_trace_rho.py (copula_table, spearman), which are checked against SciPy there.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from scipy.stats import multivariate_normal, norm

from vmsim.entities import azure_table, split


def copula_table(rho: float, p_row: np.ndarray, p_col: np.ndarray) -> np.ndarray:
    a = np.r_[-np.inf, norm.ppf(np.clip(np.cumsum(p_row)[:-1], 1e-12, 1 - 1e-12)), np.inf]
    b = np.r_[-np.inf, norm.ppf(np.clip(np.cumsum(p_col)[:-1], 1e-12, 1 - 1e-12)), np.inf]
    mvn = multivariate_normal(mean=[0, 0], cov=[[1, rho], [rho, 1]])

    def F(x, y):
        if x == -np.inf or y == -np.inf:
            return 0.0
        if x == np.inf and y == np.inf:
            return 1.0
        if x == np.inf:
            return float(norm.cdf(y))
        if y == np.inf:
            return float(norm.cdf(x))
        return float(mvn.cdf([x, y]))

    G = np.array([[F(x, y) for y in b] for x in a])
    return np.clip(G[1:, 1:] - G[:-1, 1:] - G[1:, :-1] + G[:-1, :-1], 0, None)


def spearman(tab: np.ndarray) -> float:
    """Tie-corrected (mid-rank) Spearman from a contingency table."""
    n = tab.sum()
    r, c = tab.sum(1), tab.sum(0)
    rr = np.cumsum(r) - r + (r + 1) / 2
    cr = np.cumsum(c) - c + (c + 1) / 2
    mr, mc = (r * rr).sum() / n, (c * cr).sum() / n
    cov = (tab * np.outer(rr - mr, cr - mc)).sum()
    vr, vc = (r * (rr - mr) ** 2).sum(), (c * (cr - mc) ** 2).sum()
    return float(cov / np.sqrt(vr * vc)) if vr > 0 and vc > 0 else np.nan


@lru_cache(maxsize=1)
def resident_tier_shares() -> tuple[float, ...]:
    """Tier shares, by count, of the residents present at a random instant: the population the
    engine's rho_tier_risk is computed on. Presence is length-biased (entities.
    sample_present_residents), so each resident row is weighted by its lifetime. (Before 4 Oct
    2026 this was the unweighted pool, 49/27/24%; the VMs present are about 61/4/35%.)"""
    az = azure_table()
    rows = split()["resident_rows"]
    tier = az["tier"].to_numpy()[rows]
    life = az["lifetime_s"].to_numpy(float)[rows]
    return tuple(np.bincount(tier, weights=life, minlength=3) / life.sum())


@lru_cache(maxsize=64)
def latent_to_spearman(rho_l: float, n_levels: int = 40) -> float:
    """Spearman(tier, host risk) that a latent correlation rho_l gives under the simulator's
    margins."""
    p_row = np.asarray(resident_tier_shares())
    p_col = np.full(n_levels, 1 / n_levels)
    return spearman(copula_table(float(rho_l), p_row, p_col) * 1e6)
