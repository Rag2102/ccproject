"""Week 17, task 2: numerical check of THEORY.md (T1-T4) against vmsim/theory.py's closed forms.

Monte Carlo of Delta (BAM vs P2) over (rho, s_y, q, lam, s_n, gamma), with the closed form beside
each point. Agreement tolerance, fixed here before the sweep ran: |Delta_MC - Delta_CF| <=
max(3 SE, 0.001), on the expected-benefit estimator (exact given the draws). 0.001 is a tenth of
the materiality line delta = 1%. A disagreement is a bug-hunt before it is a finding.

Checks:
  T2  Delta >= 0 at every grid point with s_n = 0 and gamma = 1 (closed form and MC within tol)
  T3  closed form = MC everywhere (tolerance above); ranking term zero at rho = 1
  T4  how Delta moves with s_n; where the ranking term changes sign (noise_flip)
  break-even  where Delta = delta = 1% in (rho, s_y), per (q, lam)

Writes results/v2/theory_check.json, theory_grid.csv; figure results/figures/v2_theory_check.pdf.
"""

from __future__ import annotations

import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmsim import theory as T  # noqa: E402

TOL_ABS = 0.001
TOL_SE = 3.0
DELTA_MAT = 0.01
RHOS = [-0.9, -0.6, -0.3, 0.0, 0.3, 0.6, 0.9]
S_Y = [0.25, 0.5, 1.0]
QS = [0.005, 0.02, 0.1, 0.5]
LAMS = [0.0, 1.0, 4.0]
S_N = [0.0, 0.5, 1.0, 2.0]
GAMMAS = [0.5, 1.0, 2.0]


def sweep(n: int, reps: int) -> pd.DataFrame:
    rows = []
    grid = list(itertools.product(RHOS, S_Y, QS, LAMS, S_N, GAMMAS))
    t = time.time()
    for i, (r, sy, q, lam, sn, g) in enumerate(grid):
        m = T.Model(rho=r, s_y=sy, q=q, lam=lam, s_n=sn, gamma=g)
        mc = T.monte_carlo(m, n=n, reps=reps, seed=i)
        cf = T.delta(m)
        rows.append(
            {
                "rho": r,
                "s_y": sy,
                "q": q,
                "lam": lam,
                "s_n": sn,
                "gamma": g,
                "delta_cf": cf,
                "delta_mc": mc["exp"]["delta"],
                "se_mc": mc["exp"]["se"],
                "delta_mc_real": mc["real"]["delta"],
                "se_mc_real": mc["real"]["se"],
                "bam_share": T.bam(m)["share"],
                "ranking_gap": T.ranking_gap(m),
            }
        )
        if (i + 1) % 200 == 0:
            print(f"{i + 1}/{len(grid)} points, {time.time() - t:.0f}s", flush=True)
    d = pd.DataFrame(rows)
    d["abs_err"] = (d["delta_mc"] - d["delta_cf"]).abs()
    d["tol"] = np.maximum(TOL_SE * d["se_mc"], TOL_ABS)
    d["agree"] = d["abs_err"] <= d["tol"]
    return d


def break_even(q: float, lam: float) -> list[dict]:
    """For each s_y, the rho values where the closed-form Delta crosses delta (no noise)."""
    s_ys = np.linspace(0.05, 1.5, 59)
    rho = np.linspace(-0.99, 0.99, 397)
    out = []
    for sy in s_ys:
        d = np.array([T.delta(T.Model(rho=r, s_y=sy, q=q, lam=lam)) for r in rho]) - DELTA_MAT
        cross = [
            float(rho[i] - d[i] * (rho[i + 1] - rho[i]) / (d[i + 1] - d[i]))
            for i in range(len(d) - 1)
            if np.sign(d[i]) != np.sign(d[i + 1])
        ]
        out.append(
            {
                "s_y": float(sy),
                "rho_cross": cross,
                "above_everywhere": bool((d > 0).all()),
                "below_everywhere": bool((d < 0).all()),
            }
        )
    return out


def figure(d: pd.DataFrame, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import figstyle

    figstyle.apply()

    fig, ax = plt.subplots(2, 2, figsize=(9, 7))
    base = (d.q == 0.02) & (d.lam == 1.0) & (d.s_n == 0) & (d.gamma == 1)
    rr = np.linspace(-0.95, 0.95, 77)
    for sy, col in zip(S_Y, ("C0", "C1", "C2"), strict=False):
        s = d[base & (d.s_y == sy)]
        ax[0, 0].errorbar(s.rho, 100 * s.delta_mc, 196 * s.se_mc, fmt="o", ms=3, color=col)
        cf = [100 * T.delta(T.Model(rho=r, s_y=sy, q=0.02, lam=1.0)) for r in rr]
        ax[0, 0].plot(rr, cf, color=col, label=f"σ_logκ = {sy}")
    ax[0, 0].set(xlabel="ρ (log p, log κ)", ylabel="Δ vs P2 (%)", title="T3: closed form and MC")
    ax[0, 0].axhline(1, ls=":", c="k", lw=0.8)
    ax[0, 0].legend(fontsize=7)

    lam0 = (d.q == 0.02) & (d.lam == 0.0) & (d.s_n == 0) & (d.gamma == 1)
    for sy, col in zip(S_Y, ("C0", "C1", "C2"), strict=False):
        s = d[lam0 & (d.s_y == sy)]
        ax[0, 1].plot(s.rho, 100 * s.delta_cf, "-o", ms=3, color=col, label=f"σ_logκ = {sy}")
    ax[0, 1].set(
        xlabel="ρ", ylabel="Δ vs P2 (%)", title="Free migration (λ = 0): ranking term only"
    )
    ax[0, 1].legend(fontsize=7)

    sn = np.linspace(0, 3, 61)
    for r, col in zip((-0.9, 0.0, 0.6), ("C3", "C0", "C2"), strict=False):
        cf = [100 * T.delta(T.Model(rho=r, s_y=0.25, q=0.02, lam=0.0, s_n=x)) for x in sn]
        ax[1, 0].plot(sn, cf, color=col, label=f"ρ = {r}, σ_logκ = 0.25, λ = 0")
        cf1 = [100 * T.delta(T.Model(rho=r, s_y=0.5, q=0.02, lam=1.0, s_n=x)) for x in sn]
        ax[1, 0].plot(sn, cf1, color=col, ls="--", label=f"ρ = {r}, σ_logκ = 0.5, λ = 1")
    ax[1, 0].axhline(0, c="k", lw=0.8)
    ax[1, 0].set(xlabel="noise SD on log p", ylabel="Δ vs P2 (%)", title="T4: noise")
    ax[1, 0].legend(fontsize=6)

    for lam, col in zip(LAMS, ("C0", "C1", "C2"), strict=False):
        be = break_even(0.02, lam)
        for b in be:
            for x in b["rho_cross"]:
                ax[1, 1].plot(x, b["s_y"], ".", color=col, ms=3)
        ax[1, 1].plot([], [], ".", color=col, label=f"λ = {lam}")
    ax[1, 1].set(
        xlabel="ρ",
        ylabel="σ_logκ",
        title="Break-even: Δ = 1% (q = 0.02)",
        xlim=(-1, 1),
    )
    ax[1, 1].legend(fontsize=7)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)


def main() -> None:
    quick = "--quick" in sys.argv
    d = sweep(n=50_000 if quick else 200_000, reps=6 if quick else 10)
    res = ROOT / "results" / "v2"
    d.to_csv(res / "theory_grid.csv", index=False)
    clean = (d.s_n == 0) & (d.gamma == 1)
    t2_cf = d[clean]["delta_cf"].min()
    t2_mc_viol = d[clean & (d.delta_mc < -d.tol)]
    flips = {}
    for r, sy in itertools.product(RHOS, S_Y):
        f = T.noise_flip(T.Model(rho=r, s_y=sy))
        if f is not None:
            flips[f"rho={r},s_y={sy}"] = f
    mono = []
    for _key, g in d[(d.gamma == 1)].groupby(["rho", "s_y", "q", "lam"]):
        g = g.sort_values("s_n")
        mono.append(bool((np.diff(g["delta_cf"].to_numpy()) <= 1e-12).all()))
    out = {
        "tolerance": {"abs": TOL_ABS, "se_multiple": TOL_SE},
        "points": int(len(d)),
        "T3_agree_share": float(d["agree"].mean()),
        "T3_disagreements": d[~d["agree"]].to_dict(orient="records"),
        "T3_max_abs_err": float(d["abs_err"].max()),
        "T2_min_delta_cf_no_noise": float(t2_cf),
        "T2_mc_violations": int(len(t2_mc_viol)),
        "T3_ranking_gap_at_rho_1": T.ranking_gap(T.Model(rho=1.0, s_y=1.0)),
        "T4_monotone_in_noise_share": float(np.mean(mono)),
        "T4_noise_flip_points": flips,
        "T4_negative_delta_points": int((d.delta_cf < 0).sum()),
        "break_even_q002": {str(lam): break_even(0.02, lam) for lam in LAMS},
    }
    (res / "theory_check.json").write_text(json.dumps(out, indent=2, default=float))
    figure(d, ROOT / "results" / "figures" / "v2_theory_check.pdf")
    print(
        json.dumps(
            {k: v for k, v in out.items() if k not in ("break_even_q002", "T3_disagreements")},
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
