"""ADR-013: destination-aware BAM (P4-net) and selective avoidance on fresh seeds 4001-4050.

Primary families N and S by the ADR's rule; noise, G0-high, the extended law, migrations and the
combined policy as secondary. Outside the confirmatory family and G3. VMSIM_SRC points at another
copy of vmsim, used only while another run must not see an edited engine.

  .venv/bin/python scripts/v2/54_selective_net.py --workers 2   # run what is missing, summarise
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, os.environ.get("VMSIM_SRC") or str(ROOT))
from vmsim import engine, scenarios, worlds  # noqa: E402
from vmsim.policies.selective import BAMNet, BAMNetSelective, SelectiveAvoid  # noqa: E402
from vmsim.policies.variants import AvoidTop  # noqa: E402
from vmsim.predictor import Scores, _expit, _logit  # noqa: E402

_spec = importlib.util.spec_from_file_location("rm", ROOT / "scripts/v2/24_run_matrix.py")
RM = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RM)

M = yaml.safe_load((ROOT / "configs/v2/matrix.yaml").read_text())
OUT = ROOT / "results" / "explore" / "selective_net"
ADR = ROOT / "docs/v2/DECISIONS/ADR-013-selective-avoidance-and-net-bam.md"
SEEDS = range(4001, 4051)
REGIMES = ("B1", "B2")
Q = (0.02, 0.05, 0.10)
W = 0.044
A_T = (0.268, 0.289, 0.443)
PHI = {"B1": 0.94, "B2": 0.75}
TIERS = {"level": (1.0, 2.0, 10 / 3), "steep": (1.0, 3.0, 10.0)}
NOISE = (0.5, 1.0)


class Persistent:
    """ADR-012's noise: Gaussian logit noise, one draw per host per 30-day block."""

    def __init__(self, oracle, sigma, streams, block=30):
        self.o, self.sigma, self.streams, self.block = oracle, sigma, streams, block

    def score(self, day, life_start=None):
        s = self.o.score(day, life_start)
        z = self.streams.gen("predictor", 9, day // self.block).normal(size=len(s.p_h))
        p = _expit(_logit(s.p_interval) + (self.sigma * z)[:, None])
        return Scores(p_h=p[:, 0], e_ttf=s.e_ttf, p_interval=p)


def prepared(regime, setting, seed):
    cell = f"{regime}@{setting}" if setting.startswith("G0") else regime
    cfg = scenarios.regime(RM.base_config(M), cell)
    if setting in TIERS:
        cfg = replace(cfg, cost=replace(cfg.cost, tier_weights=TIERS[setting]))
    return engine.prepare(worlds.generate(cfg, seed), cfg)


def row(prep, regime, seed, setting, sigma, pid, pol, pred=None, budget=0.02) -> dict:
    s = engine.run(prep, pol, predictor=pred, budget_frac=budget)
    return {
        "regime": regime,
        "seed": seed,
        "setting": setting,
        "sigma": sigma,
        "policy": pid,
        "total_cost": float(s["cost_total"]),
        "migrations": int(s["migrations"]),
        "rejected_arrivals": int(s["rejected_arrivals"]),
    }


def one(job: tuple[str, int]) -> None:
    regime, seed = job
    f = OUT / f"{regime}_{seed}.parquet"
    if f.exists():
        return
    rows = []
    for setting in ("default", "level", "steep", "G0-low", "G0-high"):
        prep = prepared(regime, setting, seed)
        rows.append(
            row(prep, regime, seed, setting, 0.0, "P0", RM.make_policy("P0", M, None), budget=0.0)
        )
        rows.append(row(prep, regime, seed, setting, 0.0, "P4", RM.make_policy("P4", M, None)))
        rows.append(row(prep, regime, seed, setting, 0.0, "P4-net", BAMNet()))
    prep = prepared(regime, "default", seed)
    orc = engine.make_predictor(prep)
    sel = [
        ("P0+selective", lambda: SelectiveAvoid(Q)),
        ("P0+avoid(W)", lambda: AvoidTop(W)),
        ("redirect(W)", lambda: SelectiveAvoid((W, W, W), name="redirect(W)")),
    ]
    for pid, mk in sel:
        rows.append(row(prep, regime, seed, "default", 0.0, pid, mk()))
    rows.append(row(prep, regime, seed, "default", 0.0, "P4-net+selective", BAMNetSelective(Q)))
    for sg in NOISE:
        pred = Persistent(orc, sg, prep.streams)
        for pid, mk in [*sel, ("P4", lambda: RM.make_policy("P4", M, None)), ("P4-net", BAMNet)]:
            rows.append(row(prep, regime, seed, "default", sg, pid, mk(), pred))
    tmp = f.with_suffix(".tmp")
    pd.DataFrame(rows).to_parquet(tmp, index=False)
    os.replace(tmp, f)


def bca(x: np.ndarray) -> list[float]:
    r = stats.bootstrap(
        (x,),
        np.mean,
        n_resamples=10_000,
        method="BCa",
        random_state=np.random.default_rng(20261102),
    )
    return [float(r.confidence_interval.low), float(r.confidence_interval.high)]


def holm(items: list[dict]) -> None:
    order = sorted(range(len(items)), key=lambda i: items[i]["p"])
    top = 0.0
    for rank, i in enumerate(order):
        top = max(top, min(1.0, items[i]["p"] * (len(items) - rank)))
        items[i]["p_holm"] = top


def wilcoxon(x: np.ndarray, alternative: str) -> float:
    return 1.0 if np.allclose(x, 0) else float(stats.wilcoxon(x, alternative=alternative).pvalue)


def summarise() -> None:
    d = pd.concat([pd.read_parquet(f) for f in sorted(OUT.glob("*.parquet"))], ignore_index=True)
    base = d[d.policy == "P0"].set_index(["regime", "setting", "seed"]).total_cost
    d["saving"] = [
        100 * (1 - c / base[(r, s, k)])
        for r, s, k, c in zip(d.regime, d.setting, d.seed, d.total_cost, strict=True)
    ]
    if d.groupby(["regime", "seed"]).size().nunique() != 1:
        raise SystemExit("incomplete rows")

    def vec(reg, setting, sigma, pid, col="saving"):
        x = d[(d.regime == reg) & (d.setting == setting) & (d.sigma == sigma) & (d.policy == pid)]
        return x.sort_values("seed")[col].to_numpy(float)

    n1, n2, n3 = [], [], []
    for reg in REGIMES:
        for st in ("default", "level", "steep", "G0-low"):
            net, p4 = vec(reg, st, 0, "P4-net"), vec(reg, st, 0, "P4")
            n1.append(
                {
                    "regime": reg,
                    "setting": st,
                    "saving": net.mean(),
                    "ci": bca(net),
                    "p": wilcoxon(net, "greater"),
                }
            )
            gap = net - p4
            if st == "default":
                n3.append(
                    {
                        "regime": reg,
                        "difference": gap.mean(),
                        "ci": bca(gap),
                        "pass": bca(gap)[0] > -1,
                    }
                )
            else:
                n2.append(
                    {
                        "regime": reg,
                        "setting": st,
                        "p4_saving": p4.mean(),
                        "difference": gap.mean(),
                        "ci": bca(gap),
                        "p": wilcoxon(gap, "greater"),
                    }
                )
    holm(n1)
    holm(n2)
    for t in n1 + n2:
        t["pass"] = bool(t["p_holm"] < 0.05 and t["ci"][0] > 0)
    a, b, c = all(t["pass"] for t in n1), all(t["pass"] for t in n2), all(t["pass"] for t in n3)
    fam_n = "confirmed" if a and b and c else "partial" if b and c else "not confirmed"

    s1, s2 = [], []
    for reg in REGIMES:
        sel, sr = (
            vec(reg, "default", 0, "P0+selective"),
            vec(reg, "default", 0, "P0+selective", "rejected_arrivals"),
        )
        for comp in ("P0+avoid(W)", "redirect(W)"):
            gap = sel - vec(reg, "default", 0, comp)
            s1.append(
                {
                    "regime": reg,
                    "against": comp,
                    "difference": gap.mean(),
                    "ci": bca(gap),
                    "pass": bca(gap)[0] > -1,
                }
            )
            r = sr - vec(reg, "default", 0, comp, "rejected_arrivals")
            s2.append(
                {
                    "regime": reg,
                    "against": comp,
                    "difference": r.mean(),
                    "ci": bca(r),
                    "p": wilcoxon(r, "less"),
                }
            )
    holm(s2)
    for t in s2:
        t["pass"] = bool(t["p_holm"] < 0.05 and t["ci"][1] < 0)
    full = all(t["pass"] for t in s1 + s2)
    part = all(t["pass"] for t in s1) and all(
        t["pass"] for t in s2 if t["against"] == "P0+avoid(W)"
    )
    fam_s = "confirmed" if full else "partial" if part else "not confirmed"

    table, R = [], json.loads((ROOT / "results/summary/avoid_law_R.json").read_text())
    for (reg, st, sg, pid), x in d.groupby(["regime", "setting", "sigma", "policy"]):
        x = x.sort_values("seed")
        ci = [0.0, 0.0] if pid == "P0" else bca(x.saving.to_numpy())
        table.append(
            {
                "regime": reg,
                "setting": st,
                "sigma": sg,
                "policy": pid,
                "saving": x.saving.mean(),
                "ci": ci,
                "migrations": x.migrations.mean(),
                "rejected": x.rejected_arrivals.mean(),
            }
        )
    r_t = sum(a_t * R[f"{q}|0.0"] for a_t, q in zip(A_T, Q, strict=True))
    law = {
        reg: {
            "predicted": 100 * PHI[reg] * r_t,
            "observed": float(vec(reg, "default", 0, "P0+selective").mean()),
        }
        for reg in REGIMES
    }
    out = ROOT / "results" / "summary" / "selective_net.json"
    out.write_text(
        json.dumps(
            {
                "rule": "ADR-013",
                "adr_sha256": hashlib.sha256(ADR.read_bytes()).hexdigest(),
                "verdict_N": fam_n,
                "verdict_S": fam_s,
                "N1": n1,
                "N2": n2,
                "N3": n3,
                "S1": s1,
                "S2": s2,
                "extended_law": law,
                "table": table,
            },
            indent=1,
            default=float,
        )
    )
    print("N:", fam_n, "S:", fam_s)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(r, s) for s in SEEDS for r in REGIMES]
    with ProcessPoolExecutor(a.workers) as ex:
        list(ex.map(one, jobs))
    summarise()


if __name__ == "__main__":
    main()
