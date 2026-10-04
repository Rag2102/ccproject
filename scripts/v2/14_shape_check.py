"""Week 12: shape of simulated host failure times (SIM_SPEC section 14, check 5).

Generates failure worlds for seeds 1-5 at the default configuration (first lives only; repairs
come with the engine in Week 13) and fits a Weibull to (a) cluster-level times between
consecutive host failures within the horizon and (b) per-host times to first failure, for the
non-disk multipliers 0, 1 and 3. Node-failure logs (LANL) are reported in the literature as
non-exponential with decreasing hazard; the comparison with a measured LANL shape is recorded
in docs/v2/SIM_SPEC.md once the data or the source has been read. The record, not a perfect
match, is the deliverable.

Writes results/v2/shape_check.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import weibull_min

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmsim import worlds  # noqa: E402
from vmsim.config import FailureConfig, SimConfig  # noqa: E402


def main() -> None:
    out = {}
    for mult in (0.0, 1.0, 3.0):
        gaps, firsts = [], []
        cfg = SimConfig(n_hosts=2_000, failure=FailureConfig(non_disk_multiplier=mult))
        T = cfg.warmup_days + cfg.horizon_days
        for seed in range(1, 6):
            w = worlds.generate(cfg, seed)
            t = np.sort(w.fail_t[w.fail_t < T])
            gaps.append(np.diff(t))
            firsts.append(t)
        g, f = np.concatenate(gaps), np.concatenate(firsts)
        g = g[g > 0]
        kg, _, sg = weibull_min.fit(g, floc=0)
        kf, _, sf = weibull_min.fit(f, floc=0)
        out[f"non_disk_{mult:g}x"] = {
            "failures_per_host_year": float(len(f) / (5 * 2_000) * 365 / T),
            "gap_weibull_shape": round(float(kg), 3),
            "gap_cv": round(float(g.std() / g.mean()), 3),
            "first_failure_weibull_shape": round(float(kf), 3),
            "n_failures": int(len(f)),
        }
        print(mult, out[f"non_disk_{mult:g}x"], flush=True)
    (ROOT / "results" / "v2").mkdir(parents=True, exist_ok=True)
    (ROOT / "results" / "v2" / "shape_check.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
