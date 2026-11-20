"""Figure F4 (plan Week 18): advantage over P2 against rho_L, regimes A1-A7, with the T3 overlay.

Panels: one per budget (1% and 2%, the confirmatory budgets; 0.5% and 5% in a second figure).
Per policy (P4, P5, P6; P3 for v1 continuity): mean regression-adjusted Delta with BCa intervals
simultaneous over the plotted points (Bonferroni over policies x 7 regimes), and per-seed Delta as
dots for P4 (the inset the plan asks for, drawn in place). Regime E is shown at rho_L = 0 as
separate markers by sigma_log_kappa.

T3 overlay (THEORY.md section 4: judged on direction, no numeric tolerance). The closed form needs
sigma_x, sigma_log_kappa, the effective rho between log p (host) and log kappa (VM), lambda and q.
They are measured on the simulator's own worlds (eval seed 1, day 0 of the horizon, VMs present):
  sigma_x       SD of log p_H over the hosts the VMs sit on
  s_y, rho      SD of log(c / w) and its correlation with log p_H over VMs
  lambda        mean(m / w) / mean(p c / w)
  q             one-shot share: the budget a 30-day decision window can spend, min(1, 30 x b)
and written to results/v2/f4_theory_params.json.

Writes results/figures/v2_F4_advantage.pdf and v2_F4_advantage_other_budgets.pdf.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import yaml
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmsim import engine, scenarios, theory, worlds  # noqa: E402
from vmsim.config import SimConfig  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle  # noqa: E402

POLICIES = {p: figstyle.C[p] for p in ("P4", "P5", "P6", "P3")}
PARAMS = ROOT / "results" / "v2" / "f4_theory_params.json"


def measure(regime: str, m: dict) -> dict:
    s = m["scale"]
    base = SimConfig(
        n_hosts=s["n_hosts"],
        horizon_days=s["horizon_days"],
        warmup_days=s["warmup_days"],
        risk_h_days=s["risk_h_days"],
        name="f4",
    )
    cfg = scenarios.regime(base, regime)
    prep = engine.prepare(worlds.generate(cfg, 1), cfg)
    pred = engine.make_predictor(prep)
    p = pred.score(cfg.warmup_days).p_h
    w = prep.world
    v = prep.vm
    n0 = len(w.vm_rows)
    lp = np.log(np.clip(p[w.vm_host], 1e-12, None))
    lk = np.log(v["fail_cost"][:n0] / v["mem"][:n0])
    mw = v["mig_cost_est"][:n0] / v["mem"][:n0]
    pk = np.exp(lp + lk)
    return {
        "s_x": float(lp.std()),
        "s_y": float(lk.std()),
        "rho": float(np.corrcoef(lp, lk)[0, 1]),
        "lam": float(mw.mean() / pk.mean()),
        "mu_x": float(lp.mean()),
    }


def params(m: dict) -> dict:
    if PARAMS.exists():
        return json.loads(PARAMS.read_text())
    out = {r: measure(r, m) for r in m["regimes"]["A"] + m["regimes"]["E"]}
    PARAMS.write_text(json.dumps(out, indent=2))
    return out


def t3(par: dict, b_pct: float) -> float:
    q = min(1.0, 30 * b_pct / 100)
    mdl = theory.Model(
        rho=par["rho"], s_y=par["s_y"], s_x=par["s_x"], mu_x=par["mu_x"], q=q, lam=par["lam"]
    )
    return theory.delta(mdl)


def bca(x: np.ndarray, level: float) -> tuple[float, float]:
    r = stats.bootstrap(
        (x,), np.mean, confidence_level=level, n_resamples=10_000, method="BCa",
        random_state=np.random.default_rng(20261004),
    )  # fmt: skip
    return float(r.confidence_interval.low), float(r.confidence_interval.high)


def draw(cells: dict, par: dict, budgets: list[float], m: dict, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figstyle.apply()
    lat = scenarios.A_LATENT
    k = len(POLICIES) * len(lat)
    fig, axes = plt.subplots(1, len(budgets), figsize=(5.2 * len(budgets), 4.2), squeeze=False)
    for ax, b in zip(axes[0], budgets, strict=True):
        for j, (pol, col) in enumerate(POLICIES.items()):
            xs, ys, lo, hi = [], [], [], []
            for r in m["regimes"]["A"]:
                c = cells.get((r, b, pol))
                if c is None:
                    continue
                adj = np.asarray(c["per_seed_adj"])
                a, z = bca(adj, 1 - 0.05 / k)
                x = lat[r] + (j - 1.5) * 0.008
                xs.append(x), ys.append(100 * adj.mean()), lo.append(100 * a), hi.append(100 * z)
                if pol == "P4":
                    ax.plot(np.full(len(adj), x), 100 * adj, ".", color=col, ms=2, alpha=0.35)
            if xs:
                ys_, lo_, hi_ = np.array(ys), np.array(lo), np.array(hi)
                ax.errorbar(xs, ys_, [ys_ - lo_, hi_ - ys_], marker=figstyle.MK[pol],
                            ls=figstyle.LS[pol], ms=3, color=col, label=pol)  # fmt: skip
        for e, mk in zip(m["regimes"]["E"], ("v", "s", "^", "D"), strict=False):
            c = cells.get((e, b, "P4"))
            if c is not None:
                ax.plot(-0.04, 100 * np.mean(c["per_seed_adj"]), mk, color="C0", ms=5,
                        label=f"P4, {e} (σκ={scenarios.E_SIGMA[e]})")  # fmt: skip
        rr = [lat[r] for r in m["regimes"]["A"]]
        ax.plot(rr, [100 * t3(par[r], b) for r in m["regimes"]["A"]], "k--", lw=1,
                label="T3, measured parameters")  # fmt: skip
        ax.axhline(1, ls=":", c="k", lw=0.8)
        ax.axhline(0, c="k", lw=0.6)
        ax.set(xlabel="ρ_L (latent)", ylabel="Δ vs P2 (%), adjusted", title=f"budget {b:g}%")
        ax.legend(fontsize=6)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)


def main() -> None:
    small = "--small" in sys.argv
    m = yaml.safe_load(
        (ROOT / "configs/v2" / ("matrix_small.yaml" if small else "matrix.yaml")).read_text()
    )
    res_root = ROOT / "results" / ("small" if small else "")
    summ = res_root / ("dryrun_summary" if "--dry-run" in sys.argv else "summary")
    global PARAMS
    if small:
        PARAMS = res_root / "f4_theory_params.json"
    cells = {}
    for g in ("A", "E"):
        f = summ / f"{g}.json"
        if not f.exists():
            continue
        for c in json.loads(f.read_text())["cells"]:
            c["per_seed_adj"] = c["per_seed_adjusted"]  # Delta - beta (F - mean F), per seed
            cells[(c["regime"], c["budget_pct"], c["policy"])] = c
    par = params(m)
    fig = res_root / "figures" if small else ROOT / "results" / "figures"
    fig.mkdir(parents=True, exist_ok=True)
    draw(cells, par, [1.0, 2.0], m, fig / "v2_F4_advantage.pdf")
    draw(cells, par, [0.5, 5.0], m, fig / "v2_F4_advantage_other_budgets.pdf")
    print(json.dumps({r: {b: round(t3(par[r], b), 4) for b in m["budgets_pct"]} for r in par}))


if __name__ == "__main__":
    main()
