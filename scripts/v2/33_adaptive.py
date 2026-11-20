"""Week 21, task 1: P6 on regime D (adaptive track, RQ4) and figure F8.

Per budget and eval seed, from the frozen matrix's records for D (P0, P2, P4 and P6):
  regret        C_P6 - min(C_P2, C_P4): against the better fixed policy in hindsight
  captured      (C_P0 - C_P6) / (C_P0 - min(C_P2, C_P4)): share of the better policy's benefit
  vs P2         (C_P2 - C_P6) / C_P2
  switches      number of mode changes, and the detection delay: days from the mid-run shift
                (rho_L 0.1 -> 0.6, calibration drift starts) to P6's first switch after it
H4 targets (plan Week 21): captured >= 90% and never more than 1% worse than P2. Reported per
seed and as the share of seeds meeting each.
Writes results/summary/adaptive_D.json and results/figures/v2_F8_adaptive.pdf.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]


def cost(root: Path, pct: float, pid: str, seed: int) -> dict | None:
    f = root / "D" / "D" / f"b{pct:g}" / pid / f"s{seed:04d}.json"
    return json.loads(f.read_text()) if f.exists() else None


def analyse(root: Path, m: dict) -> dict:
    sc = m["scale"]
    shift = sc["warmup_days"] + sc["horizon_days"] // 2
    end = sc["warmup_days"] + sc["horizon_days"]
    a, b = m["seeds"]["eval"]
    out = {"shift_day": shift, "end_day": end, "budgets": {}}
    for pct in m["budgets_pct"]:
        rows = []
        for s in range(a, b + 1):
            r0, r2, r4, r6 = (
                cost(root, 0 if p == "P0" else pct, p, s) for p in ("P0", "P2", "P4", "P6")
            )
            if not all((r0, r2, r4, r6)):
                continue
            c0, c2, c4, c6 = (r["metrics"]["total_cost"] for r in (r0, r2, r4, r6))
            best = min(c2, c4)
            sw = [(int(d), to) for d, to in r6["policy"]["params"].get("switches", [])]
            after = [d for d, _ in sw if d >= shift]
            rows.append(
                {
                    "seed": s,
                    "C_P0": c0,
                    "C_P2": c2,
                    "C_P4": c4,
                    "C_P6": c6,
                    "regret": c6 - best,
                    "regret_rel": (c6 - best) / best,
                    "captured": (c0 - c6) / (c0 - best) if c0 > best else None,
                    "vs_P2": (c2 - c6) / c2,
                    "switches": sw,
                    "n_switches": len(sw),
                    "detection_delay_days": (after[0] - shift) if after else None,
                    "days_bam": r6["policy"]["params"].get("mode_days", {}).get("BAM"),
                }
            )
        if not rows:
            continue
        cap = [r["captured"] for r in rows if r["captured"] is not None]
        delays = [r["detection_delay_days"] for r in rows if r["detection_delay_days"] is not None]
        out["budgets"][str(pct)] = {
            "n": len(rows),
            "regret_rel_mean": float(np.mean([r["regret_rel"] for r in rows])),
            "captured_median": float(np.median(cap)) if cap else None,
            "share_captured_ge_90pct": float(np.mean([c >= 0.9 for c in cap])) if cap else None,
            "vs_P2_mean": float(np.mean([r["vs_P2"] for r in rows])),
            "share_not_worse_than_P2_by_1pct": float(np.mean([r["vs_P2"] >= -0.01 for r in rows])),
            "switches_mean": float(np.mean([r["n_switches"] for r in rows])),
            "detection_delay_median_days": float(np.median(delays)) if delays else None,
            "seeds_without_switch_after_shift": int(
                sum(r["detection_delay_days"] is None for r in rows)
            ),
            "per_seed": rows,
        }
    return out


def figure(res: dict, path: Path, pct: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import figstyle

    figstyle.apply()
    b = res["budgets"].get(pct)
    if not b:
        return
    fig, ax = plt.subplots(1, 3, figsize=(10, 3.4), gridspec_kw={"width_ratios": [2.2, 1, 1]})
    rows = b["per_seed"]
    for i, r in enumerate(rows):
        t, mode = 0, "P2"
        for d, to in r["switches"] + [(res["end_day"], None)]:
            ax[0].barh(
                i,
                d - t,
                left=t,
                color=figstyle.C["P4"] if mode == "BAM" else figstyle.C["P2"],
                height=0.8,
            )
            t, mode = d, to
    ax[0].axvline(res["shift_day"], color="k", ls="--", lw=1)
    ax[0].set(xlabel="day", ylabel="eval seed", title=f"P6 mode by day (D, {pct}%): BAM vs P2")
    caps = [r["captured"] for r in rows if r["captured"] is not None]
    ax[1].hist(caps, bins=12, color=figstyle.C["P6"])
    ax[1].axvline(0.9, color="k", ls="--", lw=1)
    ax[1].set(xlabel="share of better policy's benefit", title="H4: ≥ 90%")
    ax[2].hist([100 * r["vs_P2"] for r in rows], bins=12, color=figstyle.C["P6"])
    ax[2].axvline(-1, color="k", ls="--", lw=1)
    ax[2].set(xlabel="Δ vs P2 (%)", title="H4: never < −1%")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--small", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    m = yaml.safe_load(
        (ROOT / "configs/v2" / ("matrix_small.yaml" if a.small else "matrix.yaml")).read_text()
    )
    res_root = ROOT / "results" / ("small" if a.small else "")
    root = res_root / ("dryrun" if a.dry_run else "raw")
    out = res_root / ("dryrun_summary" if a.dry_run else "summary")
    out.mkdir(parents=True, exist_ok=True)
    res = analyse(root, m)
    (out / "adaptive_D.json").write_text(json.dumps(res, indent=1, default=float))
    fig_dir = res_root / "figures" if (a.small or a.dry_run) else ROOT / "results" / "figures"
    figure(
        res,
        fig_dir / "v2_F8_adaptive.pdf",
        "2" if "2" in res["budgets"] else next(iter(res["budgets"]), "2"),
    )
    keys = ("n", "captured_median", "share_not_worse_than_P2_by_1pct", "switches_mean")
    print({k: {kk: v[kk] for kk in keys} for k, v in res["budgets"].items()})


if __name__ == "__main__":
    main()
