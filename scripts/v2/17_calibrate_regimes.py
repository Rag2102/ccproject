"""Week 14 follow-up: calibrate each rho regime's arrival blend (vmsim/scenarios.py).

With the world's initial blend, arrivals overshoot: the VMs present at A3 have Spearman 0.475
against the 0.256 target (P0; the pilot's 0.217 was an average over policies, and migrating
policies lower the correlation by moving VMs to safer hosts). For each rho cell, bisection on
the arrival blend (dev seed 101, 2,000 hosts, 30 + 120 days, P0) so the horizon mean hits the
target within 0.01.

Writes results/v2/regime_calibration.json.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmsim import scenarios  # noqa: E402
from vmsim.config import SimConfig  # noqa: E402

CELLS = ["A2", "A3", "A4", "A5", "A6", "A7", "B1", "B1-high", "D0"]


def main() -> None:
    base = SimConfig(n_hosts=2_000, horizon_days=120, name="calib")
    out = {}
    for cell in CELLS:
        cfg = scenarios.regime(base, cell, calibrated=False)
        if cfg.placement.regime != "rho":
            continue
        t = time.time()
        b, r, tries = scenarios.calibrate_arrival_blend(cfg)
        out[cell] = {
            "target_spearman": cfg.placement.rho,
            "arrival_blend": round(b, 4),
            "achieved": round(r, 4),
            "tries": tries,
            "hosts": base.n_hosts,
            "days": base.warmup_days + base.horizon_days,
            "seed": 101,
        }
        print(
            f"{cell}: target {cfg.placement.rho} blend {b:.3f} achieved {r:.3f} "
            f"({time.time() - t:.0f}s)",
            flush=True,
        )
    path = ROOT / "results" / "v2" / "regime_calibration.json"
    path.write_text(json.dumps(out, indent=2))
    print("wrote", path)


if __name__ == "__main__":
    main()
