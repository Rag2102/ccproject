"""BAM, budget-aware migration (P4) and its variants (plan Week 15; PROTOCOL section 2).

For each eligible VM i on host j:
    b_i = p_j c_i e_i - m_i,
  p_j   the host's probability of failing within H days (the predictor's p_H);
  c_i   interruption cost, tier weight x D_fail, times s_i, the probability that i is still
        running at a failure (survival-weighted by default, SIM_SPEC section 10);
  e_i   the probability that i's migration finishes before the host fails, given the
        migrations already queued on the host: exp(-lambda_j t), lambda_j = -ln(1 - p_j) / H
        per day and t = the queue ahead of i in its lane plus i's own duration;
  m_i   migration cost (blackout + resource minutes).
VMs are ranked by b_i / w_i and taken while b_i > 0. After each pick, e is recomputed for the
rest of that host's queue (a lazy max-heap). The engine applies the GB budget in this order and
reserves destination capacity as it goes.

Weights: "gb" (P4, w = memory GB, the budgeted resource), "time" (BAM-time, w = NIC-seconds)
and "cost" (BAM-cost, w = m; v2's rule, an ablation only).

Ablation flags (plan Week 15): urgency=False sets e = 1; c_uniform / m_uniform replace c_i / m_i
by constants (--no-criticality, --uniform-migration-cost); p_only ranks by p_j alone.
With uniform c and m, no urgency and p_only, BAM selects VMs on hosts with p_j > m / c, riskiest
host first, in the within-host order: exactly P2 with tau = m / c (tested decision for decision).
"""

from __future__ import annotations

import heapq

import numpy as np

from vmsim.policies.base import Observation, Policy, top_hosts_mask, within_host_key


class BAM(Policy):
    def __init__(
        self,
        weight: str = "gb",
        urgency: bool = True,
        survival: bool = True,
        c_uniform: float | None = None,
        m_uniform: float | None = None,
        p_only: bool = False,
        order: str = "random",
        lanes: int = 2,
        name: str | None = None,
    ):
        if weight not in ("gb", "time", "cost"):
            raise ValueError(f"unknown weight {weight!r}")
        self.weight, self.urgency, self.survival = weight, urgency, survival
        self.c_uniform, self.m_uniform, self.p_only = c_uniform, m_uniform, p_only
        self.order, self.lanes = order, lanes
        self.name = name or {"gb": "P4", "time": "P4-time", "cost": "P4-cost"}[weight]

    # ---------------------------------------------------------------- terms
    def terms(self, obs: Observation) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """(p, c, m, w) per eligible VM."""
        p = obs.p_h[obs.vm_host]
        if self.c_uniform is not None:
            c = np.full(len(obs.vm), float(self.c_uniform))
        else:
            c = obs.vm_fail_cost * (obs.vm_survival if self.survival else 1.0)
        m = (
            np.full(len(obs.vm), float(self.m_uniform))
            if self.m_uniform is not None
            else obs.vm_mig_cost
        )
        w = {"gb": obs.vm_mem_gb, "time": obs.vm_mig_s, "cost": np.maximum(m, 1e-9)}[self.weight]
        return p, c, m, w

    def benefit(self, obs: Observation, e: np.ndarray | float = 1.0) -> np.ndarray:
        p, c, m, _ = self.terms(obs)
        return p * c * e - m

    # ---------------------------------------------------------------- decision
    def decide(self, obs: Observation, budget_gb: float) -> np.ndarray:
        p, c, m, w = self.terms(obs)
        b0 = p * c - m  # e <= 1, so b0 bounds b from above
        if self.p_only:
            # the threshold rule's ordering (top_hosts_mask and the same within-host draw)
            ok_host = np.zeros(len(obs.p_h), dtype=bool)
            ok_host[obs.vm_host[b0 > 0]] = True
            mask = top_hosts_mask(obs, -obs.p_h, ok_host, budget_gb) & (b0 > 0)
            key = within_host_key(obs, self.order)[mask]
            if not mask.any():
                return np.zeros(0, dtype=np.int64)
            idx = np.lexsort((key, obs.vm_host[mask], -p[mask]))
            return obs.vm[mask][idx]
        cand = np.flatnonzero(b0 > 0)
        if len(cand) == 0:
            return np.zeros(0, dtype=np.int64)
        if not self.urgency:
            dens = b0[cand] / w[cand]
            tie = within_host_key(obs, self.order)[cand]
            return obs.vm[cand[np.lexsort((tie, -dens))]]
        return obs.vm[self._greedy_queue(obs, cand, p, c, m, w, budget_gb)]

    def _greedy_queue(self, obs, cand, p, c, m, w, budget_gb) -> np.ndarray:
        h_days = obs.h_days
        lam = -np.log1p(-np.clip(p, 0, 1 - 1e-12)) / h_days  # per day
        dur_d = obs.vm_mig_s / 86_400.0
        host = obs.vm_host
        ahead: dict[int, float] = {}  # host -> queued duration (days) per lane
        version: dict[int, int] = {}
        tie = within_host_key(obs, self.order)

        def density(i):
            t = ahead.get(int(host[i]), 0.0) + dur_d[i]
            b = p[i] * c[i] * np.exp(-lam[i] * t) - m[i]
            return b, b / w[i]

        heap = []
        for i in cand:
            b, dn = density(i)
            if b > 0:
                heap.append((-dn, tie[i], int(i), 0))
        heapq.heapify(heap)
        out, gb = [], 0.0
        limit = 3 * budget_gb + 200.0  # the engine stops at the budget; this bounds the work
        while heap and gb < limit:
            _, _, i, ver = heapq.heappop(heap)
            h = int(host[i])
            if ver != version.get(h, 0):  # the host's queue grew since: recompute
                b, dn = density(i)
                if b > 0:
                    heapq.heappush(heap, (-dn, tie[i], i, version.get(h, 0)))
                continue
            out.append(i)
            gb += obs.vm_mem_gb[i]
            ahead[h] = ahead.get(h, 0.0) + dur_d[i] / self.lanes
            version[h] = version.get(h, 0) + 1
        return np.array(out, dtype=np.int64)


def uniform_constants(d_fail_min: float = 10.0) -> tuple[float, float]:
    """(c, m) constants for --no-criticality and --uniform-migration-cost: the means over
    resident Azure VMs at the default cost and migration settings."""
    from vmsim import migration
    from vmsim.config import CostConfig, MigrationConfig
    from vmsim.entities import azure_table, split

    t = azure_table().iloc[split()["resident_rows"]]
    cc, mc = CostConfig(d_fail_min=d_fail_min), MigrationConfig()
    w = np.asarray(cc.tier_weights)[t["tier"].to_numpy()]
    dur, blk, _ = migration.precopy(
        t["memory_gb"].to_numpy(float),
        migration.dirty_mbps(t["avg_cpu"].to_numpy(float), mc),
        migration.host_bw_mbps(mc) / mc.max_concurrent,
        mc,
    )
    return float((w * cc.d_fail_min).mean()), float(
        migration.migration_cost_min(w, dur, blk, cc).mean()
    )
