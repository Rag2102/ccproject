"""Week 16, task 7: P6 smoke on regime D and on the pure-noise control; regret.

Conditions (dev seeds 101-105, 2,000 hosts x 365 days + 30 warm-up, budget 2%):
  D       regime D (rho_L 0.1 -> 0.6 at mid-run) with the drifting predictor (gamma 1 -> 0.7
          over the second half);
  noise   regime A3 with the pure-noise predictor (scores shuffled across hosts daily);
  A3      regime A3 with the oracle predictor (reference).
Policies: P2 (cost-tuned threshold from the Week 14 pilot, A3 at 2%), P4 (BAM) and P6.
Regret of P6 = its cost minus the better of P2 and P4 in hindsight, per seed.

Done when (plan): P6 switches in the intended direction on D, never on the noise control.
Writes results/v2/guard_smoke_w16.json and _runs.csv.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmsim import engine, scenarios, worlds  # noqa: E402
from vmsim.config import SimConfig  # noqa: E402
from vmsim.policies.bam import BAM  # noqa: E402
from vmsim.policies.guard import SafeGuard  # noqa: E402
from vmsim.policies.reference import Threshold  # noqa: E402

SEEDS = range(101, 106)
CONDITIONS = {"D": ("D", "drift"), "noise": ("A3", "noise"), "A3": ("A3", "oracle")}


def p2_from_pilot() -> tuple[float, str]:
    pilot = json.loads((ROOT / "results" / "v2" / "pilot_w14.json").read_text())
    t = pilot["p2"]["A3@0.02"]["cost"]
    return float(t["tau"]), t["order"]


def main() -> None:
    tau, order = p2_from_pilot()
    rows, switches = [], {}
    for cond, (cell, kind) in CONDITIONS.items():
        cfg = scenarios.regime(SimConfig(n_hosts=2_000, horizon_days=365, name="g"), cell)
        for seed in SEEDS:
            prep = engine.prepare(worlds.generate(cfg, seed), cfg)
            pred = engine.make_predictor(prep, kind, gamma=0.7)
            guard = SafeGuard(Threshold(tau, order, "P2"))
            for pol in (Threshold(tau, order, "P2"), BAM(), guard):
                s = engine.run(prep, pol, predictor=pred, budget_frac=0.02, predictor_label=kind)
                rows.append(
                    {
                        "condition": cond,
                        "seed": seed,
                        "policy": pol.name,
                        "cost_total": s["cost_total"],
                        "migrations": s["migrations"],
                        "rho_horizon": s["rho_tier_risk_horizon"],
                    }
                )
            switches[f"{cond}/{seed}"] = {
                "mode_days": guard.mode_days,
                "switches": [
                    {
                        k: sw[k]
                        for k in ("day", "from", "to", "delta_hat", "lower", "slope", "events")
                    }
                    for sw in guard.switches
                ],
            }
            print(
                cond,
                seed,
                guard.mode_days,
                [(x["day"], x["to"]) for x in guard.switches],
                flush=True,
            )
    runs = pd.DataFrame(rows)
    c = runs.pivot_table(index=["condition", "seed"], columns="policy", values="cost_total")
    c["best_fixed"] = c[["P2", "P4"]].min(axis=1)
    c["regret_P6"] = c["P6"] - c["best_fixed"]
    c["regret_P6_rel"] = c["regret_P6"] / c["best_fixed"]
    summary = {
        cond: {
            "mean_cost": g[["P2", "P4", "P6"]].mean().round(1).to_dict(),
            "regret_P6_mean": float(g["regret_P6"].mean()),
            "regret_P6_rel_mean": float(g["regret_P6_rel"].mean()),
            "p6_beats_p2_seeds": int((g["P6"] < g["P2"]).sum()),
            "switches_per_seed": [
                len(switches[f"{cond}/{s}"]["switches"]) for s in g.index.get_level_values(1)
            ],
        }
        for cond, g in c.groupby(level=0)
    }
    out = ROOT / "results" / "v2"
    runs.to_csv(out / "guard_smoke_w16_runs.csv", index=False)
    (out / "guard_smoke_w16.json").write_text(
        json.dumps(
            {"p2": {"tau": tau, "order": order}, "summary": summary, "switches": switches},
            indent=2,
            default=float,
        )
    )
    print(json.dumps(summary, indent=1, default=float))


if __name__ == "__main__":
    main()
