"""Week 15, task 7: behaviour smoke for P4 and P5 (budget use and migrations per day only).

Five dev seeds (101-105), regime A3, 2,000 hosts x 365 days, budget 2%. Reports, per policy:
budget utilisation, migrations per day, the share of days the budget binds, rejected arrivals
and, for P5, the actions chosen. **Not the winner:** costs are recorded in the CSV but this run
decides nothing (plan Week 15).

Writes results/v2/behaviour_smoke_w15.json and _runs.csv.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmsim import engine, scenarios, worlds  # noqa: E402
from vmsim.config import SimConfig  # noqa: E402
from vmsim.policies.bam import BAM  # noqa: E402
from vmsim.policies.narya import Narya  # noqa: E402

SEEDS = range(101, 106)


def main() -> None:
    cfg = scenarios.regime(SimConfig(n_hosts=2_000, horizon_days=365, name="smoke"), "A3")
    rows, actions = [], {}
    for seed in SEEDS:
        prep = engine.prepare(worlds.generate(cfg, seed), cfg)
        for pol in (BAM(), BAM("time"), BAM("cost"), Narya("simple"), Narya("faithful")):
            with tempfile.TemporaryDirectory() as d:
                s = engine.run(prep, pol, budget_frac=0.02, out_dir=Path(d))
                daily = pd.read_parquet(Path(d) / "daily.parquet")
            daily = daily[daily["day"] >= cfg.warmup_days]
            rows.append(
                {
                    "seed": seed,
                    "policy": pol.name,
                    "budget_utilisation": s["budget_utilisation"],
                    "migrations_per_day": s["migrations"] / cfg.horizon_days,
                    "share_days_budget_binds": float(
                        (daily["gb_planned"] >= 0.95 * daily["budget_gb"]).mean()
                    ),
                    "share_days_no_migration": float((daily["n_planned"] == 0).mean()),
                    "rejected_arrivals": s["rejected_arrivals"],
                    "cost_total": s["cost_total"],
                }
            )
            if isinstance(pol, Narya):
                actions.setdefault(pol.name, []).append(pol.action_counts())
        print(f"seed {seed} done", flush=True)
    runs = pd.DataFrame(rows)
    out = ROOT / "results" / "v2"
    runs.to_csv(out / "behaviour_smoke_w15_runs.csv", index=False)
    summ = runs.drop(columns="seed").groupby("policy").mean().round(4)
    print(summ.to_string())
    (out / "behaviour_smoke_w15.json").write_text(
        json.dumps({"by_policy": summ.to_dict(orient="index"), "p5_actions": actions}, indent=2)
    )


if __name__ == "__main__":
    main()
