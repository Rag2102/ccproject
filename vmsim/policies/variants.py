"""Exploratory policy variants written after the Week 18 results (5 Oct 2026; post-freeze).

None of these is in the frozen matrix or the confirmatory family. They exist to explain the
Week 18 finding that the Narya-inspired P5 saves more than BAM against never migrating
(`docs/v2/RESULTS_W18.md`), and are logged in `docs/v2/CHANGES_AFTER_FREEZE.md`.

  AvoidTop   P0 plus avoid-allocation: every day, mark the riskiest `share` of up hosts so they
             take no new VMs (the action P5 has and no other policy has). Migrates nothing.
  BAMAvoid   BAM (P4) plus the same avoid-allocation marks.
  BAMWait    BAM that judges each move over the re-decision window instead of the full risk
             horizon: p_d = 1 - (1 - p_H)^(d / H). Moving today forgoes the option to decide again
             tomorrow; with d = H it is P4. (Survival weighting is left at the H/2 value.)
P6 with P0 as its fallback needs no new class: SafeGuard(Never(), BAM()).
"""

from __future__ import annotations

import numpy as np

from vmsim.policies.bam import BAM
from vmsim.policies.base import Observation, Policy


def top_risk_mark(obs: Observation, share: float) -> np.ndarray:
    """The riskiest `share` of hosts that are up or already avoided, by p_H (at least one)."""
    up = obs.host_up | (obs.host_avoid if obs.host_avoid is not None else False)
    ups = np.flatnonzero(up)
    mark = np.zeros(len(obs.p_h), dtype=bool)
    if len(ups) == 0 or share <= 0:
        return mark
    k = max(1, int(round(share * len(ups))))
    mark[ups[np.argsort(-obs.p_h[ups], kind="stable")[:k]]] = True
    return mark


class AvoidTop(Policy):
    def __init__(self, share: float = 0.02, name: str = "P0+avoid"):
        self.share, self.name = share, name

    def decide(self, obs: Observation, budget_gb: float) -> np.ndarray:
        return np.zeros(0, dtype=np.int64)

    def avoid(self, obs: Observation) -> np.ndarray:
        return top_risk_mark(obs, self.share)


class BAMAvoid(BAM):
    def __init__(self, share: float = 0.02, name: str = "P4+avoid", **kw):
        super().__init__(name=name, **kw)
        self.share = share

    def avoid(self, obs: Observation) -> np.ndarray:
        return top_risk_mark(obs, self.share)


class BAMWait(BAM):
    def __init__(self, window_days: float = 7.0, name: str | None = None, **kw):
        super().__init__(name=name or f"P4-wait{window_days:g}", **kw)
        self.window_days = window_days

    def terms(self, obs: Observation):
        p, c, m, w = super().terms(obs)
        h = getattr(self, "_h_full", obs.h_days)  # the full risk horizon H of p_H
        frac = min(1.0, self.window_days / h)
        return 1.0 - np.power(1.0 - np.clip(p, 0.0, 1.0), frac), c, m, w

    def decide(self, obs: Observation, budget_gb: float) -> np.ndarray:
        # p_d over the window; the queue model's hazard is -ln(1 - p_d) / d = -ln(1 - p_H) / H,
        # so presenting the window as the horizon keeps e consistent
        self._h_full = obs.h_days
        return super().decide(_with_horizon(obs, self.window_days), budget_gb)


def _with_horizon(obs: Observation, d: float) -> Observation:
    from dataclasses import replace

    return replace(obs, h_days=int(round(min(d, obs.h_days))))
