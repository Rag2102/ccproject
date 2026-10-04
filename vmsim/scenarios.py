"""Regime cells (PROTOCOL section 3) as configurations.

A1-A7: latent Gaussian copula, rho_L in {0, .15, .3, .45, .6, .75, .9}, converted to the
       Spearman target of placement.rho_controlled under the simulator's margins (copula.py);
B1:    rank copula at the Week 8 measurement (G1_decision.md): rho_L at the median over cells
       and at the lowest lower bound / highest upper bound (B1-low, B1, B1-high);
D:     non-stationary: rho_L 0.1 until mid-run, then 0.6, with calibration drift (gamma 1 to
       0.7 over the second half: engine.make_predictor(prep, "drift", gamma=0.7));
C:     adversarial. B2 and E come with their weeks.

Daily batches of arrivals placed with the world's initial blend overshoot the target (A3: 0.475
for the VMs present against 0.256), so each rho cell has its own arrival blend, calibrated on
dev seed 101 with P0 so that the VMs present over the horizon hit the target:
results/v2/regime_calibration.json, written by scripts/v2/17_calibrate_regimes.py.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from vmsim.config import SimConfig
from vmsim.copula import latent_to_spearman

A_LATENT = {f"A{i + 1}": r for i, r in enumerate((0.0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9))}
# Week 8, M1 and the platform proxy, latent axis (results/v2/trace_rho_table.csv): cells a, b, h
# point -0.015 / 0.007 / 0.027 (median 0.007); lowest lower bound -0.019, highest upper 0.056
B1_LATENT = {"B1-low": -0.019, "B1": 0.007, "B1-high": 0.056}
D_LATENT = (0.1, 0.6)  # regime D: rho_L before and after mid-run (PROTOCOL section 3)
E_SIGMA = {"E1": 0.25, "E2": 0.5, "E3": 1.0}  # regime E: SD of log kappa at rho = 0
CALIBRATION = Path(__file__).resolve().parents[1] / "results" / "v2" / "regime_calibration.json"
B2_CLASSES = CALIBRATION.with_name("b2_classes.json")


def second_source_latent() -> float | None:
    """Week 21 second placement source (Google 2019 cell f): its latent rho_L point estimate
    under the primary choices (M1, platform proxy, placement weights, tau-b), from
    scripts/v2/13_trace_rho.py --analyse-second. None until that has run."""
    f = CALIBRATION.with_name("trace_rho_second_table.csv")
    if not f.exists():
        return None
    import pandas as pd

    d = pd.read_csv(f)
    d = d[
        (d.mapping == "M1") & (d.proxy == "risk_platform") & (d.weight == "n") & (d.stat == "tau_b")
    ]
    return float(d["latent"].iloc[0]) if len(d) else None


def latent_of(cell: str) -> float | None:
    if cell == "D0":  # calibration entry for regime D's first half
        return D_LATENT[0]
    if cell == "B1-f":  # Week 21 second source, B-style placement at cell f's measured rho_L
        return second_source_latent()
    return A_LATENT.get(cell, B1_LATENT.get(cell))


def _calibrated(cell: str, n_hosts: int) -> float | None:
    if not CALIBRATION.exists():
        return None
    tab = json.loads(CALIBRATION.read_text())
    row = tab.get(cell)
    return None if row is None else row["arrival_blend"]


def regime(base: SimConfig, cell: str, calibrated: bool = True) -> SimConfig:
    pc = base.placement
    lat = latent_of(cell)
    if cell == "A1":
        p = replace(pc, regime="random", rho=0.0, arrival_blend=None)
    elif lat is not None:
        rho = round(latent_to_spearman(lat), 4)
        if rho <= 0:  # negative or zero targets: random placement (the blend cannot go below 0)
            p = replace(pc, regime="random", rho=0.0, arrival_blend=None)
        else:
            ab = _calibrated(cell, base.n_hosts) if calibrated else None
            p = replace(pc, regime="rho", rho=rho, arrival_blend=ab)
    elif cell == "D":
        # rho_L 0.1 until mid-run, then 0.6 (= A5); pair it with make_predictor(.., "drift")
        rho0 = round(latent_to_spearman(D_LATENT[0]), 4)
        mid = base.warmup_days + base.horizon_days // 2
        p = replace(
            pc,
            regime="rho",
            rho=rho0,
            arrival_blend=_calibrated("D0", base.n_hosts) if calibrated else None,
            arrival_blend_after=_calibrated("A5", base.n_hosts) if calibrated else None,
            switch_day=mid,
        )
    elif cell == "C":
        p = replace(pc, regime="adversarial", arrival_blend=None)
    elif cell == "B2":
        shares, cgt = b2_tables()
        p = replace(
            pc, regime="class", arrival_blend=None, class_shares=shares, class_given_tier=cgt
        )
    elif cell in E_SIGMA:
        # heterogeneity only: random placement, spread of log(c / w) set (PROTOCOL section 3)
        p = replace(pc, regime="random", rho=0.0, arrival_blend=None)
        cost = replace(base.cost, kappa_sigma=E_SIGMA[cell])
        return replace(base, placement=p, cost=cost, name=f"{base.name}-{cell}")
    else:
        raise ValueError(f"unknown regime {cell!r}")
    return replace(base, placement=p, name=f"{base.name}-{cell}")


def calibrate_arrival_blend(cfg: SimConfig, seed: int = 101, steps: int = 8, tol: float = 0.01):
    """Bisection on the arrival blend in [0, 1] so the horizon mean of Spearman(tier, risk) over
    the VMs present hits cfg.placement.rho, with P0 (migrations move VMs to safer hosts and so
    lower the correlation; the regime is defined without them). Returns (blend, achieved,
    tries)."""
    from vmsim import engine, worlds
    from vmsim.policies.reference import Never

    w = worlds.generate(cfg, seed)
    target = cfg.placement.rho
    tries = []

    def achieved(b):
        c = replace(cfg, placement=replace(cfg.placement, arrival_blend=b))
        r = engine.run(engine.prepare(w, c), Never(), budget_frac=0.0)["rho_tier_risk_horizon"]
        tries.append((round(b, 4), round(r, 4)))
        return r

    lo, hi = 0.0, 1.0  # achieved rho rises with the blend
    best = (lo, np.inf)
    for _ in range(steps):
        mid = (lo + hi) / 2
        r = achieved(mid)
        if abs(r - target) < abs(best[1] - target):
            best = (mid, r)
        if abs(r - target) <= tol:
            break
        lo, hi = (mid, hi) if r < target else (lo, mid)
    return best[0], best[1], tries


__all__ = ["A_LATENT", "B1_LATENT", "regime", "calibrate_arrival_blend", "latent_of", "np"]


def ipf(seed: np.ndarray, rows: np.ndarray, cols: np.ndarray, iters: int = 200) -> np.ndarray:
    """Iterative proportional fitting: scale seed to the row and column margins, keeping its
    odds ratios."""
    j = seed.astype(float).copy()
    for _ in range(iters):
        j *= (rows / j.sum(1))[:, None]
        j *= cols / j.sum(0)
    return j


def b2_tables() -> tuple[tuple[float, ...], tuple[tuple[float, ...], ...]]:
    """Regime B2 from results/v2/b2_classes.json (scripts/v2/23_b2_classes.py): machine shares of
    the classes (lowest risk first) and P(class | tier). The trace's class x tier table is fitted
    to the class shares and the simulator's resident tier shares, keeping the trace's odds ratios
    (the association is replayed, not the trace's tier margin)."""
    from vmsim.copula import resident_tier_shares

    cl = json.loads(B2_CLASSES.read_text())["classes"]
    m = np.array([c["machine_share"] for c in cl])
    m = m / m.sum()
    mix = np.array([c["tier_mix_low_med_high"] for c in cl])
    j = ipf(m[:, None] * mix, m, np.asarray(resident_tier_shares(), float))
    cgt = (j / j.sum(0)).T  # rows: tier; columns: class
    return tuple(float(x) for x in m), tuple(tuple(float(x) for x in r) for r in cgt)
