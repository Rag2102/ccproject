"""Tuning P2 on dev seeds (PROTOCOL section 2; plan Week 14).

P2 is the threshold rule with a tuned tau and the best of three within-host orders, tuned on
dev seeds 101-110 only (never eval or pilot seeds). Two criteria:

  "budget"  the protocol v0.2 text ("tau tuned by bisection ... to use the budget"): for each
            order, the largest tau whose mean budget utilisation is >= target_util (0.95, the
            protocol's 5% reporting rule), by bisection on log10(tau); the order with the
            lowest mean cost wins.
  "cost"    proposed in Week 14 (not yet in the protocol): for each order, the tau on a
            log grid with the lowest mean cost over the dev seeds; the lowest of the three
            wins. The grid includes a tau above every score, so P2 can never be worse than P0
            on the dev seeds.

The pilot (scripts/v2/16_pilot.py) runs both so the choice can be made on evidence.
"""

from __future__ import annotations

import numpy as np

from vmsim import engine
from vmsim.policies.reference import Threshold

DEV_SEEDS = tuple(range(101, 111))
ORDERS = ("smallest", "largest", "random")
COST_GRID = tuple(np.round(10 ** np.linspace(-3.5, 0, 15), 8)) + (2.0,)  # 2.0: never migrate


def _evaluate(preps, budget_frac, tau, order):
    rs = [engine.run(p, Threshold(tau, order, "P2"), budget_frac=budget_frac) for p in preps]
    return (
        float(np.mean([r["budget_utilisation"] for r in rs])),
        float(np.mean([r["cost_total"] for r in rs])),
    )


def tune_p2(
    preps: list,
    budget_frac: float,
    criterion: str = "budget",
    target_util: float = 0.95,
    orders=ORDERS,
    lo: float = -6.0,
    hi: float = 0.0,
    steps: int = 12,
    grid=COST_GRID,
) -> dict:
    """preps: engine.Prepared for each dev seed. Returns tau, order and the per-order table."""
    table = []
    for order in orders:
        if criterion == "cost":
            res = [(t, *_evaluate(preps, budget_frac, t, order)) for t in grid]
            t, u, c = min(res, key=lambda r: r[2])
            table.append({"order": order, "tau": t, "util": u, "cost": c, "reached": True})
            continue
        if criterion != "budget":
            raise ValueError(f"unknown criterion {criterion!r}")
        a, b = lo, hi  # utilisation is non-increasing in tau
        ua, ca = _evaluate(preps, budget_frac, 10**a, order)
        if ua < target_util:
            table.append({"order": order, "tau": 10**a, "util": ua, "cost": ca, "reached": False})
            continue
        best = (10**a, ua, ca)
        for _ in range(steps):
            mid = (a + b) / 2
            u, c = _evaluate(preps, budget_frac, 10**mid, order)
            if u >= target_util:
                a, best = mid, (10**mid, u, c)
            else:
                b = mid
        table.append(
            {"order": order, "tau": best[0], "util": best[1], "cost": best[2], "reached": True}
        )
    win = min(table, key=lambda r: r["cost"])
    return {
        "criterion": criterion,
        "tau": win["tau"],
        "order": win["order"],
        "budget_frac": budget_frac,
        "table": table,
    }
