"""ADR-012 setup: the distribution of host risk p_H that avoidance sees, dev seeds only.

Writes results/summary/avoid_risk_dist.json: SD of log p_H across up hosts (the sigma_x of T5) and
the empirical share of risk held by the riskiest q of hosts, for B1 and B2.

  .venv/bin/python scripts/v2/51_avoid_risk_dist.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmsim import engine, scenarios, worlds  # noqa: E402

_spec = importlib.util.spec_from_file_location("rm", ROOT / "scripts/v2/24_run_matrix.py")
RM = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RM)
M = yaml.safe_load((ROOT / "configs/v2/matrix.yaml").read_text())
SEEDS = range(101, 106)
QS = [0.005, 0.01, 0.02, 0.05, 0.10]


def main() -> None:
    out = {}
    for reg in ("B1", "B2"):
        cfg = scenarios.regime(RM.base_config(M), reg)
        sds, tops = [], {q: [] for q in QS}
        for seed in SEEDS:
            prep = engine.prepare(worlds.generate(cfg, seed), cfg)
            pred = engine.make_predictor(prep)
            for day in range(cfg.warmup_days, cfg.warmup_days + cfg.horizon_days, 30):
                p = np.asarray(pred.score(day).p_h, float)
                p = p[p > 0]
                sds.append(float(np.std(np.log(p))))
                s = np.sort(p)[::-1]
                for q in QS:
                    tops[q].append(float(s[: max(1, int(round(q * len(s))))].sum() / s.sum()))
        out[reg] = {"sigma_x": float(np.mean(sds)), "sigma_x_sd": float(np.std(sds)),
                    "top_share": {str(q): float(np.mean(v)) for q, v in tops.items()},
                    "seeds": list(SEEDS)}  # fmt: skip
    f = ROOT / "results" / "summary" / "avoid_risk_dist.json"
    f.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
