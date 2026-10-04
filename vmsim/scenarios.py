"""Regime cells (PROTOCOL section 3) as configurations.

A1-A7: latent Gaussian copula, rho_L in {0, .15, .3, .45, .6, .75, .9}, converted to the
       Spearman target of placement.rho_controlled under the simulator's margins (copula.py);
C:     adversarial. B1/B2 need the Week 8 measurement; D and E come with their weeks.
"""

from __future__ import annotations

from dataclasses import replace

from vmsim.config import SimConfig
from vmsim.copula import latent_to_spearman

A_LATENT = {f"A{i + 1}": r for i, r in enumerate((0.0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9))}


def regime(base: SimConfig, cell: str) -> SimConfig:
    pc = base.placement
    if cell == "A1":
        p = replace(pc, regime="random", rho=0.0)
    elif cell in A_LATENT:
        p = replace(pc, regime="rho", rho=round(latent_to_spearman(A_LATENT[cell]), 4))
    elif cell == "C":
        p = replace(pc, regime="adversarial")
    else:
        raise ValueError(f"regime {cell!r} is not available yet (B1/B2 after Week 8)")
    return replace(base, placement=p, name=f"{base.name}-{cell}")
