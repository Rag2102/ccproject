"""Week 20 analysis: ablations (F6), robustness grid and F7, Morris ranking, where BAM loses.

Inputs: results/raw/W20/{ablation,robust,morris}.parquet and W20/failure/
(scripts/v2/26_run_w20.py),
plus the main matrix cells for P2 and P4 (results/raw/{A,B}/). All exploratory (PROTOCOL v1.0
section 9). Deltas are paired by seed: (C_ref - C_pi) / C_ref, with 95% BCa intervals.
Writes results/summary/w20_{ablation,robustness,morris,failure}.json and figures
results/figures/v2_F6_ablations.pdf, v2_F7_heatmap.pdf, v2_morris.pdf.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("w20", ROOT / "scripts/v2/26_run_w20.py")
w20 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(w20)
from vmsim import morris, scenarios, worlds  # noqa: E402

RAW, SUMM, FIG = (
    ROOT / "results" / "raw",
    ROOT / "results" / "summary",
    ROOT / "results" / "figures",
)


def bca(x: np.ndarray) -> list[float]:
    if len(x) < 3 or np.allclose(x, x[0]):
        return [float(np.mean(x))] * 2
    r = stats.bootstrap(
        (x,),
        np.mean,
        n_resamples=10_000,
        method="BCa",
        random_state=np.random.default_rng(20261004),
    )
    return [float(r.confidence_interval.low), float(r.confidence_interval.high)]


def paired(ref: pd.Series, pol: pd.Series) -> dict:
    j = pd.concat([ref.rename("ref"), pol.rename("pol")], axis=1).dropna()
    x = ((j["ref"] - j["pol"]) / j["ref"]).to_numpy()
    return {
        "n": int(len(x)),
        "delta_mean": float(x.mean()) if len(x) else None,
        "ci95": bca(x) if len(x) else None,
    }


def main_cells() -> pd.DataFrame:
    parts = [pd.read_parquet(f) for g in ("A", "B") for f in (RAW / g).glob("*_P[24].parquet")]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


# --------------------------------------------------------------------------- ablation
def ablation(main: pd.DataFrame) -> dict:
    f = RAW / "W20" / "ablation.parquet"
    if not f.exists() or main.empty:
        return {}
    d = pd.read_parquet(f)
    out = []
    for (reg, b, pol), g in d.groupby(["regime", "budget_pct", "policy"]):
        c = g.set_index("seed")["total_cost"]
        ref = main[(main.regime == reg) & (main.budget_pct == b)]
        p2 = ref[ref.policy == "P2"].set_index("seed")["total_cost"]
        p4 = ref[ref.policy == "P4"].set_index("seed")["total_cost"]
        out.append(
            {
                "regime": reg,
                "budget_pct": float(b),
                "variant": pol,
                "vs_P2": paired(p2, c),
                "vs_full_BAM": paired(p4, c),
            }
        )
    return {"cells": out}


def fig_ablation(res: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import figstyle

    figstyle.apply()

    if not res:
        return
    d = pd.DataFrame(
        [
            {
                **{k: c[k] for k in ("regime", "budget_pct", "variant")},
                "m": c["vs_full_BAM"]["delta_mean"],
                "lo": c["vs_full_BAM"]["ci95"][0],
                "hi": c["vs_full_BAM"]["ci95"][1],
            }
            for c in res["cells"]
        ]
    )
    regs = sorted(d.regime.unique())
    fig, ax = plt.subplots(1, len(regs), figsize=(3.4 * len(regs), 3.6), sharey=True, squeeze=False)
    for j, r in enumerate(regs):
        g = d[d.regime == r]
        for k, (b, h) in enumerate(g.groupby("budget_pct")):
            y = np.arange(len(h)) + 0.2 * k
            ax[0, j].errorbar(
                100 * h.m,
                y,
                xerr=[100 * (h.m - h.lo), 100 * (h.hi - h.m)],
                fmt="o",
                ms=3,
                label=f"{b:g}%",
            )
            ax[0, j].set_yticks(np.arange(len(h)), h.variant)
        ax[0, j].axvline(0, c="k", lw=0.8)
        ax[0, j].set(title=r, xlabel="Δ vs full BAM (%)")
    ax[0, 0].legend(fontsize=7, title="budget")
    fig.tight_layout()
    fig.savefig(FIG / "v2_F6_ablations.pdf")


# --------------------------------------------------------------------------- robustness
def robustness(main: pd.DataFrame) -> dict:
    f = RAW / "W20" / "robust.parquet"
    if not f.exists():
        return {}
    d = pd.read_parquet(f)
    out = []
    for (setting, reg), g in d.groupby(["setting", "regime"]):
        p2 = g[g.policy == "P2"].set_index("seed")["total_cost"]
        row = {"setting": setting, "regime": reg}
        for pol in sorted(set(g.policy) - {"P2", "P0"}):
            row[pol] = paired(p2, g[g.policy == pol].set_index("seed")["total_cost"])
        out.append(row)
    base = []
    for reg in ("A3", "B1"):
        ref = main[(main.regime == reg) & (main.budget_pct == 2)] if not main.empty else main
        if len(ref):
            base.append(
                {
                    "setting": "base",
                    "regime": reg,
                    "P4": paired(
                        ref[ref.policy == "P2"].set_index("seed")["total_cost"],
                        ref[ref.policy == "P4"].set_index("seed")["total_cost"],
                    ),
                }
            )
    return {"cells": out + base}


def fig_f7(res: dict, w: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import figstyle

    figstyle.apply()

    if not res:
        return
    f7 = w["robustness"]["f7"]
    bws, gs = [0.5, 1.0, 1.5], [0.5, 1.0, 2.0]
    by = {(c["setting"], c["regime"]): c for c in res["cells"]}

    def get(bw, g):
        if bw == 1.0 and g == 1.0:
            name = "base"
        elif g == 1.0:
            name = f"bw_{bw:g}"
        elif bw == 1.0:
            name = f"gamma_{g:g}"
        else:
            name = f"f7_bw{bw}_g{g}"
        c = by.get((name, f7["regime"]))
        return np.nan if c is None or "P4" not in c else 100 * c["P4"]["delta_mean"]

    z = np.array([[get(bw, g) for bw in bws] for g in gs])
    fig, ax = plt.subplots(figsize=(4.4, 3.6))
    im = ax.imshow(z, cmap="RdYlGn", origin="lower")
    for i in range(3):
        for j in range(3):
            if np.isfinite(z[i, j]):
                ax.text(j, i, f"{z[i, j]:+.1f}", ha="center", va="center", fontsize=9)
    ax.set_xticks(range(3), [f"{b:g}x" for b in bws])
    ax.set_yticks(range(3), [f"γ={g:g}" for g in gs])
    ax.set(
        xlabel="real bandwidth / assumed",
        ylabel="miscalibration",
        title=f"Δ BAM vs P2 (%), {f7['regime']} 2%",
    )
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(FIG / "v2_F7_heatmap.pdf")


# --------------------------------------------------------------------------- morris
def morris_rank(w: dict) -> dict:
    f = RAW / "W20" / "morris.parquet"
    if not f.exists():
        return {}
    d = pd.read_parquet(f)
    names, traj = w20.morris_design(w)
    r, n, _ = traj.shape
    y = np.full((r, n), np.nan)
    for row in d.itertuples():
        y[row.t, row.j] = row.delta_mean
    full = ~np.isnan(y).any(axis=1)
    if not full.any():
        return {"complete_trajectories": 0}
    rows = morris.summarise(morris.effects(traj[full], y[full]), names)
    return {
        "complete_trajectories": int(full.sum()),
        "output": "Delta of BAM vs P2 (A3)",
        "ranking": rows,
    }


def fig_morris(res: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import figstyle

    figstyle.apply()

    if not res.get("ranking"):
        return
    fig, ax = plt.subplots(figsize=(4.8, 3.8))
    for r in res["ranking"]:
        ax.plot(r["mu_star"], r["sigma"], "o", color="#12a150")
        ax.annotate(
            r["factor"],
            (r["mu_star"], r["sigma"]),
            fontsize=7,
            xytext=(3, 3),
            textcoords="offset points",
        )
    ax.set(
        xlabel="μ* (influence)", ylabel="σ (non-linearity / interaction)", title="Morris screening"
    )
    fig.tight_layout()
    fig.savefig(FIG / "v2_morris.pdf")


# --------------------------------------------------------------------------- failure analysis
def host_costs(run_dir: Path, t0: float, t1: float, n_hosts: int) -> np.ndarray:
    o = pd.read_parquet(run_dir / "outcomes.parquet")
    o = o[(o.t >= t0) & (o.t < t1)]
    c = np.zeros(n_hosts)
    hit = o[o.kind.isin(["interrupt", "transient"])]
    np.add.at(c, hit.host.astype(int).to_numpy(), hit.cost.to_numpy())
    mig = o[(o.kind == "migration") & (o.status != "dropped")]
    np.add.at(c, mig.src.astype(int).to_numpy(), mig.cost.to_numpy())
    return c


def failure(m: dict, w: dict) -> dict:
    fa = w["failure_analysis"]
    root = RAW / "W20" / "failure"
    if not root.exists():
        return {}
    rows = []
    for reg in fa["regimes"]:
        cfg = scenarios.regime(w20.rm.base_config(m), reg)
        t0, t1 = cfg.warmup_days, cfg.warmup_days + cfg.horizon_days
        for s in w20.seeds_of(fa["seeds"]):
            world = worlds.generate(cfg, s)
            n = len(world.fail_t)
            age = world.age0.mean(axis=1) if world.age0.ndim == 2 else world.age0
            hi = np.bincount(world.vm_host, weights=(world.vm_tier == 2).astype(float), minlength=n)
            cnt = np.bincount(world.vm_host, minlength=n)
            high_share = np.divide(hi, cnt, out=np.zeros(n), where=cnt > 0)
            for b in fa["budgets_pct"]:
                d2, d4 = (root / reg / f"b{b:g}" / p / f"s{s:04d}" for p in ("P2", "P4"))
                if not (d2 / "outcomes.parquet").exists() or not (d4 / "outcomes.parquet").exists():
                    continue
                diff = host_costs(d4, t0, t1, n) - host_costs(d2, t0, t1, n)
                rows.append(
                    pd.DataFrame(
                        {
                            "regime": reg,
                            "seed": s,
                            "budget_pct": b,
                            "age": age,
                            "high_share": high_share,
                            "risk0": world.host_risk0,
                            "diff": diff,
                        }
                    )
                )
    if not rows:
        return {}
    d = pd.concat(rows, ignore_index=True)
    d["age_decile"] = d.groupby(["regime", "seed"])["age"].transform(
        lambda x: pd.qcut(x, 10, labels=False, duplicates="drop")
    )
    d["risk_decile"] = d.groupby(["regime", "seed"])["risk0"].transform(
        lambda x: pd.qcut(x.rank(method="first"), 10, labels=False)
    )
    d["tier_tertile"] = pd.cut(
        d["high_share"], [-0.01, 0.2, 0.4, 1.01], labels=["low", "mid", "high"]
    )

    def summary(key):
        g = d.groupby(["regime", "budget_pct", key], observed=True)["diff"]
        return [
            {
                "regime": r,
                "budget_pct": float(b),
                key: str(k),
                "mean_cost_diff_per_host": float(v),
                "bam_worse": bool(v > 0),
            }
            for (r, b, k), v in g.mean().items()
        ]

    return {
        "note": "diff = BAM cost - P2 cost per host over the horizon (interruptions on the "
        "host plus migrations out of it); positive means BAM is worse there",
        "by_age_decile": summary("age_decile"),
        "by_risk_decile": summary("risk_decile"),
        "by_tier_tertile": summary("tier_tertile"),
    }


def main() -> None:
    m, w = w20.load()
    SUMM.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    main_c = main_cells()
    ab = ablation(main_c)
    rb = robustness(main_c)
    mo = morris_rank(w)
    fa = failure(m, w)
    for name, res in (("ablation", ab), ("robustness", rb), ("morris", mo), ("failure", fa)):
        (SUMM / f"w20_{name}.json").write_text(json.dumps(res, indent=1, default=float))
    fig_ablation(ab)
    fig_f7(rb, w)
    fig_morris(mo)
    print(
        {
            "ablation_cells": len(ab.get("cells", [])),
            "robustness_cells": len(rb.get("cells", [])),
            "morris_trajectories": mo.get("complete_trajectories", 0),
            "failure": bool(fa),
        }
    )


if __name__ == "__main__":
    main()
