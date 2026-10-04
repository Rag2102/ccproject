"""Paired statistics for the frozen matrix (PROTOCOL.md v1.0 section 5). Plan Weeks 18-19.

For each cell (regime, budget, policy) against P2 on the same seeds:
  Delta_s      (C_P2,s - C_pi,s) / C_P2,s, positive when pi is better
  adjusted     Delta_s - beta (F_s - mean F), beta from OLS of Delta on the realised host
               failures F_s (identical across policies under CRN); the decision uses this one
  BCa 95% CI   scipy.stats.bootstrap (paired, 10,000 resamples); for confirmatory cells also the
               Bonferroni-simultaneous interval at 1 - 0.05 / 30
  Wilcoxon     one-sided signed-rank p (H1: Delta > 0) on the adjusted Delta
  Holm         over the confirmatory comparisons present; "partial" until all 30 exist
  win          mean adjusted Delta >= delta (1%) and Holm-adjusted p < 0.05
  SD rule      ADR-007: any confirmatory SD(Delta) > 1.6% at n = 30 triggers the extension to 50
Also: benefit captured (C_P0 - C_pi) / (C_P0 - C_P7), missed failures, unnecessary migrations,
budget utilisation (with the unspent share where > 5%, PROTOCOL section 2).

Writes results/summary/<group>.json per group, results/summary/confirmatory.json and the
vmconsole/1 summary results/summary/vmconsole.json (validated against vmmbench/schemas).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmmbench.validate import check  # noqa: E402

DELTA = 0.01
ALPHA = 0.05
SD_BOUND = {30: 0.016, 50: 0.021, 100: 0.031}
SEED_BOOT = 20261004


def load(root: Path, groups: list[str]) -> pd.DataFrame:
    parts = [pd.read_parquet(f) for g in groups for f in sorted((root / g).glob("*.parquet"))]
    if not parts:
        raise SystemExit(f"no collected cells under {root} for {groups}")
    return pd.concat(parts, ignore_index=True)


def bca(x: np.ndarray, level: float) -> list[float | None]:
    if len(x) < 3 or np.allclose(x, x[0]):
        return [float(x.mean()), float(x.mean())] if len(x) else [None, None]
    r = stats.bootstrap(
        (x,),
        np.mean,
        confidence_level=level,
        n_resamples=10_000,
        method="BCa",
        random_state=np.random.default_rng(SEED_BOOT),
    )
    lo, hi = r.confidence_interval
    return [float(lo), float(hi)]


def holm(p: dict) -> dict:
    keys = sorted(p, key=p.get)
    m, out, run = len(keys), {}, 0.0
    for i, k in enumerate(keys):
        run = max(run, min(1.0, (m - i) * p[k]))
        out[k] = run
    return out


def cell_stats(d: pd.DataFrame, conf: dict) -> list[dict]:
    rows = []
    p0 = d[d.policy == "P0"].set_index(["regime", "seed"])["total_cost"]
    for (regime, b), g in d[d.policy != "P0"].groupby(["regime", "budget_pct"]):
        piv = g.pivot_table(index="seed", columns="policy", values="total_cost")
        if "P2" not in piv:
            continue
        fails = g[g.policy == "P2"].set_index("seed")["realised_failures"].reindex(piv.index)
        c0 = p0.xs(regime, level="regime").reindex(piv.index) if regime in p0.index else None
        c7 = piv.get("P7")
        for pol in piv.columns:
            if pol == "P2":
                continue
            ok = piv[[pol, "P2"]].dropna().index
            x = ((piv.loc[ok, "P2"] - piv.loc[ok, pol]) / piv.loc[ok, "P2"]).to_numpy()
            f = fails.loc[ok].to_numpy(float)
            fc = f - f.mean()
            beta = float((fc * (x - x.mean())).sum() / (fc * fc).sum()) if (fc * fc).sum() else 0.0
            adj = x - beta * fc
            confirm = (
                pol in conf["policies"] and regime in conf["regimes"] and b in conf["budgets_pct"]
            )
            try:
                w = float(stats.wilcoxon(adj, alternative="greater").pvalue)
            except ValueError:
                w = None
            sub = g[g.policy == pol]
            rec = {
                "regime": regime,
                "budget_pct": float(b),
                "policy": pol,
                "n_seeds": int(len(x)),
                "delta_mean": float(x.mean()),
                "delta_adjusted": float(adj.mean()),
                "delta_sd": float(x.std(ddof=1)) if len(x) > 1 else None,
                "ci_bca": bca(adj, 0.95),
                "ci_bca_simultaneous": bca(adj, 1 - ALPHA / 30) if confirm else None,
                "wilcoxon_p": w,
                "beta_failures": beta,
                "family": "confirmatory" if confirm else "exploratory",
                "provenance": "SIMULATED",
                "per_seed_delta": [round(float(v), 6) for v in x],
                "per_seed_adjusted": [round(float(v), 6) for v in adj],
                "seeds": [int(v) for v in ok],
                "utilisation_mean": float(sub["utilisation"].mean()),
                "unspent_share_mean": float(max(0.0, 1 - sub["utilisation"].mean())),
                "missed_failures_mean": float(sub["missed_failures"].mean()),
                "unnecessary_migrations_mean": float(sub["unnecessary_migrations"].mean()),
                "migrations_mean": float(sub["migrations"].mean()),
                "overspend_runs": int(sub["overspend"].sum()),
            }
            if c0 is not None and c7 is not None:
                cap = (c0 - piv[pol]) / (c0 - c7)
                rec["benefit_captured_mean"] = float(cap.mean())
            rows.append(rec)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--groups", nargs="+", default=["A", "E"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    m = yaml.safe_load((ROOT / "configs/v2/matrix.yaml").read_text())
    conf = m["confirmatory"]
    root = ROOT / "results" / ("dryrun" if a.dry_run else "raw")
    out = ROOT / "results" / ("dryrun_summary" if a.dry_run else "summary")
    out.mkdir(parents=True, exist_ok=True)

    d = load(root, a.groups)
    rows = cell_stats(d, conf)
    fam = {
        (r["regime"], r["budget_pct"], r["policy"]): r["wilcoxon_p"]
        for r in rows
        if r["family"] == "confirmatory" and r["wilcoxon_p"] is not None
    }
    adj = holm({k: v for k, v in fam.items()}) if fam else {}
    n_family = len(conf["policies"]) * len(conf["regimes"]) * len(conf["budgets_pct"])
    for r in rows:
        k = (r["regime"], r["budget_pct"], r["policy"])
        r["holm_p"] = adj.get(k)
        r["win"] = (
            bool(r["delta_adjusted"] >= DELTA and adj[k] < ALPHA)
            if k in adj
            else (None if r["family"] == "confirmatory" else None)
        )
    n = max((r["n_seeds"] for r in rows), default=0)
    bound = SD_BOUND.get(n)
    sd_flags = [
        {k: r[k] for k in ("regime", "budget_pct", "policy", "delta_sd")}
        for r in rows
        if r["family"] == "confirmatory" and bound and r["delta_sd"] and r["delta_sd"] > bound
    ]
    for g in a.groups:
        regs = set(m["regimes"][g])
        part = [r for r in rows if r["regime"] in regs]
        (out / f"{g}.json").write_text(json.dumps({"group": g, "cells": part}, indent=1))
    confirm = {
        "family_size": n_family,
        "present": len(fam),
        "holm_scope": "complete" if len(fam) == n_family else "partial (provisional)",
        "sd_bound": bound,
        "sd_rule_triggered": sd_flags,
        "cells": [r for r in rows if r["family"] == "confirmatory"],
    }
    (out / "confirmatory.json").write_text(json.dumps(confirm, indent=1))
    shas = sorted(set(d["git_sha"]))
    console = {
        "schema": "vmconsole/1",
        "run": {
            "git_sha": shas[0] if len(shas) == 1 else ",".join(shas),
            "config_hash": "",
            "protocol_tag": "protocol-v1.0",
            "seeds": [int(d.seed.min()), int(d.seed.max())],
        },
        "cells": [
            {
                k: r[k]
                for k in (
                    "regime",
                    "budget_pct",
                    "policy",
                    "n_seeds",
                    "delta_mean",
                    "delta_adjusted",
                    "ci_bca",
                    "holm_p",
                    "wilcoxon_p",
                    "win",
                    "family",
                    "provenance",
                )
            }
            for r in rows
        ],
    }
    check(console, "vmconsole")
    (out / "vmconsole.json").write_text(json.dumps(console, indent=1))
    print(
        f"{len(rows)} cells; confirmatory present {len(fam)} of {n_family}; "
        f"SD rule flags: {len(sd_flags)}"
    )


if __name__ == "__main__":
    main()
