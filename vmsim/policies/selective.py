"""Exploratory policies of ADR-013 (2 Nov 2026; post-freeze, outside the confirmatory family).

  SelectiveAvoid  the riskiest q_t of up hosts are closed to tier t only; the host stays open to
                  the other tiers. Nothing migrates. Needs the engine's `tier_block` hook.
  BAMNet          BAM that charges the destination's risk: b = (p_src e - p_dst) c - m, where p_dst
                  is what the engine's destination rule delivers, the lower risk of two random up
                  hosts. P4's b assumes a moved VM is safe, and it decides afresh every day.
"""

from __future__ import annotations

import numpy as np

from vmsim.policies.bam import BAM
from vmsim.policies.base import Observation, Policy


def tier_mask(obs: Observation, q: tuple[float, float, float]) -> np.ndarray:
    """Per tier, per host: closed to new VMs of that tier (shape 3 x hosts)."""
    ups = np.flatnonzero(obs.host_up)
    order = ups[np.argsort(-obs.p_h[ups], kind="stable")]
    mask = np.zeros((3, len(obs.p_h)), dtype=bool)
    for t, share in enumerate(q):
        k = int(round(share * len(ups)))
        if k:
            mask[t, order[:k]] = True
    return mask


def expected_destination_risk(obs: Observation) -> float:
    """E[min(p_a, p_b)] over two independent uniform draws among up hosts."""
    p = np.sort(obs.p_h[obs.host_up])
    n = len(p)
    return float(p @ ((2 * (n - 1 - np.arange(n)) + 1) / n**2)) if n else 0.0


class SelectiveAvoid(Policy):
    def __init__(self, q=(0.02, 0.05, 0.10), name: str = "P0+selective"):
        self.q, self.name = tuple(q), name

    def decide(self, obs: Observation, budget_gb: float) -> np.ndarray:
        return np.zeros(0, dtype=np.int64)

    def tier_block(self, obs: Observation) -> np.ndarray:
        return tier_mask(obs, self.q)


class BAMNet(BAM):
    def __init__(self, name: str = "P4-net", **kw):
        super().__init__(name=name, **kw)

    def terms(self, obs: Observation):
        p, c, m, w = super().terms(obs)
        return p, c, m + expected_destination_risk(obs) * c, w


class BAMNetSelective(BAMNet):
    def __init__(self, q=(0.02, 0.05, 0.10), name: str = "P4-net+selective", **kw):
        super().__init__(name=name, **kw)
        self.q = tuple(q)

    def tier_block(self, obs: Observation) -> np.ndarray:
        return tier_mask(obs, self.q)
