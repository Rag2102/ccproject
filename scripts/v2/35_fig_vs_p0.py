"""F4b (ADR-005 companion to F4): the A and E cells against never migrating (P0).

F4 shows Delta against the budget-tuned P2, which can cost several times more than doing nothing,
so F4 alone says little about whether a policy helps. F4b shows each policy's mean per-seed saving
against P0, (C_P0 - C) / C_P0, with 95% BCa intervals, along rho_L (A1-A7) and, at rho_L = 0, for
the cost-spread regimes E1-E3 (hollow markers left of 0, sigma_kappa = 0.25, 0.5, 1.0 from left to
right). P2 is off the scale; its range is in each panel title. Descriptive. When
results/summary/explore_avoid.json exists (ADR-010, exploratory), avoidance without migration
(P0+avoid) is drawn too; it spends no budget, so its 2% runs stand in every panel.

Reads results/summary/vs_p0.json (34_vs_p0.py); writes results/figures/v2_F4b_vs_p0.pdf.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "v2"))
import figstyle  # noqa: E402

from vmsim import scenarios  # noqa: E402

POLS = {"P3": "v1 rule (P3)", "P4": "BAM (P4)", "P5": "Narya-inspired (P5)", "P6": "Guard (P6)"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--small", action="store_true")
    ap.add_argument("--budgets", nargs="+", type=float, default=[1.0, 2.0])
    a = ap.parse_args()
    res = ROOT / "results" / ("small" if a.small else "")
    cells = json.loads((res / "summary" / "vs_p0.json").read_text())["cells"]
    by = {(c["regime"], c["budget_pct"], c["policy"]): c for c in cells}
    pols = dict(POLS)
    xa = res / "summary" / "explore_avoid.json"
    if xa.exists():
        pols = {"P0+avoid": "Avoid risky hosts (expl.)", **POLS}
        for c in json.loads(xa.read_text())["cells"]:
            if c["policy"] == "P0+avoid":
                for b in a.budgets:  # no budget is spent: the 2% runs hold for every budget
                    by[(c["regime"], b, "P0+avoid")] = c
    figstyle.apply()
    fig, axes = plt.subplots(
        1, len(a.budgets), figsize=(figstyle.TEXT_WIDTH_IN, 2.6), sharey=True, squeeze=False
    )
    for ax, b in zip(axes[0], a.budgets, strict=True):
        for i, (p, label) in enumerate(pols.items()):
            xs, ys, lo, hi = [], [], [], []
            for r, lat in scenarios.A_LATENT.items():
                c = by.get((r, b, p))
                if c:
                    xs.append(lat + (i - 1.5) * 0.008)
                    ys.append(100 * c["saving_vs_p0_mean"])
                    lo.append(100 * (c["saving_vs_p0_mean"] - c["ci_bca"][0]))
                    hi.append(100 * (c["ci_bca"][1] - c["saving_vs_p0_mean"]))
            if xs:
                ax.errorbar(xs, ys, yerr=[lo, hi], color=figstyle.C[p], marker=figstyle.MK[p],
                            ls=figstyle.LS[p], ms=3, capsize=0, label=label)  # fmt: skip
            for j, (e, mk) in enumerate(zip(("E1", "E2", "E3"), ("v", "s", "^"), strict=True)):
                c = by.get((e, b, p))
                if c:
                    ax.plot(-0.11 + 0.025 * j, 100 * c["saving_vs_p0_mean"], mk, ms=4,
                            color=figstyle.C[p], mfc="none")  # fmt: skip
        ax.axhline(0, color="black", lw=0.8)
        keys = [(r, b, "P2") for r in scenarios.A_LATENT]
        p2 = [by[k]["saving_vs_p0_mean"] for k in keys if k in by]
        title = f"budget {b:g}%"
        if p2:
            title += f"  (P2: {100 * max(p2):+.0f}% to {100 * min(p2):+.0f}%, off scale)"
        ax.set_title(title)
        ax.set_xlabel(r"$\rho_L$ (latent)")
        ax.set_xlim(-0.14, 0.95)
    axes[0][0].set_ylabel("saving vs never migrating (%)")
    axes[0][0].legend(loc="lower right", frameon=False)
    out = res / "figures" / "v2_F4b_vs_p0.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    print(out.relative_to(ROOT))


if __name__ == "__main__":
    main()
