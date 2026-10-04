"""Week 12: shape of simulated host failure times (SIM_SPEC section 14, check 5).

Generates failure worlds for seeds 1-5 at the default configuration and fits a Weibull to
(a) cluster-level times between consecutive host failures within the horizon, (b) per-host
times to first failure and (c) per-node times between failures, with repairs (Week 13: a
repaired host gets new drives and fails again; uptime = repair to next failure), for the
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
from vmsim import failure, worlds  # noqa: E402
from vmsim.config import FailureConfig, SimConfig  # noqa: E402
from vmsim.rng import Streams  # noqa: E402


def main() -> None:
    out = {}
    for mult in (0.0, 1.0, 3.0):
        gaps, firsts, uptimes = [], [], []
        cfg = SimConfig(n_hosts=2_000, failure=FailureConfig(non_disk_multiplier=mult))
        T = cfg.warmup_days + cfg.horizon_days
        for seed in range(1, 6):
            w = worlds.generate(cfg, seed)
            t = np.sort(w.fail_t[w.fail_t < T])
            gaps.append(np.diff(t))
            firsts.append(t)
            sch = failure.lives(w, cfg.failure, worlds.n_days(cfg), Streams(seed))
            sch = sch[sch["t_fail"] < T]
            for h in np.unique(sch["host"]):
                r = np.sort(sch[sch["host"] == h], order="t_fail")
                if len(r) > 1:  # uptime from return to service to the next failure
                    uptimes.append(r["t_fail"][1:] - np.ceil(r["t_repair"][:-1]))
        g, f = np.concatenate(gaps), np.concatenate(firsts)
        u = np.concatenate(uptimes) if uptimes else np.zeros(0)
        g = g[g > 0]
        kg, _, sg = weibull_min.fit(g, floc=0)
        kf, _, sf = weibull_min.fit(f, floc=0)
        out[f"non_disk_{mult:g}x"] = {
            "failures_per_host_year": float(len(f) / (5 * 2_000) * 365 / T),
            "gap_weibull_shape": round(float(kg), 3),
            "gap_cv": round(float(g.std() / g.mean()), 3),
            "first_failure_weibull_shape": round(float(kf), 3),
            "n_failures": int(len(f)),
            "repeat_failures": int(len(u)),
        }
        if len(u) >= 20:
            ku, _, _ = weibull_min.fit(u[u > 0], floc=0)
            out[f"non_disk_{mult:g}x"]["node_uptime_weibull_shape"] = round(float(ku), 3)
            out[f"non_disk_{mult:g}x"]["node_uptime_median_days"] = round(float(np.median(u)), 1)
        print(mult, out[f"non_disk_{mult:g}x"], flush=True)
    (ROOT / "results" / "v2").mkdir(parents=True, exist_ok=True)
    (ROOT / "results" / "v2" / "shape_check.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
