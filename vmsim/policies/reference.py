"""Reference policies (plan Week 14; PROTOCOL section 2).

P0 never; P1 fixed threshold tau = 0.0073; P2 tuned threshold (tau and within-host order from
`tune.tune_p2` on dev seeds); P3 v1's cost-sensitive rule; P7 oracle; P8 random. BAM (P4) and its
variants come in Week 15-16.
"""

from __future__ import annotations

import numpy as np

from vmsim.policies.base import Policy, top_hosts_mask, within_host_key

V1_TAU = 0.0073  # v1: 95th percentile of p_fail_within_window (rounded as in the protocol)
URGENCY_CAP = 5.0  # v1 policy.py
MIN_TTF_FLOOR_DAYS = 1.0


class Never(Policy):
    """P0."""

    name = "P0"

    def decide(self, obs, budget_gb):
        return np.zeros(0, dtype=np.int64)


class Threshold(Policy):
    """P1 / P2: VMs on hosts with p_H >= tau, riskiest host first, then a within-host order."""

    def __init__(self, tau: float = V1_TAU, order: str = "random", name: str = "P1"):
        self.tau, self.order, self.name = float(tau), order, name

    def decide(self, obs, budget_gb):
        p = obs.p_h[obs.vm_host]
        m = top_hosts_mask(obs, -obs.p_h, obs.p_h >= self.tau, budget_gb)
        if not m.any():
            return np.zeros(0, dtype=np.int64)
        key = within_host_key(obs, self.order)[m]
        idx = np.lexsort((key, obs.vm_host[m], -p[m]))
        return obs.vm[m][idx]


def urgency(e_ttf: np.ndarray, h_days: int) -> np.ndarray:
    ttf = np.maximum(np.asarray(e_ttf, float), MIN_TTF_FLOOR_DAYS)
    return np.clip(h_days / ttf, 1.0, URGENCY_CAP)


class V1Rule(Policy):
    """P3: v1's per-host rule p x F x urgency > M, F = sum of c_i (survival-weighted by default,
    SIM_SPEC section 10) and M = sum of m_i over the host's eligible VMs. Hosts that pass, by net
    expected saving (p F u - M) descending; within a host, random order."""

    name = "P3"

    def __init__(self, survival_weighted: bool = True):
        self.sw = survival_weighted

    def decide(self, obs, budget_gb):
        n = len(obs.p_h)
        c = obs.vm_fail_cost * (obs.vm_survival if self.sw else 1.0)
        F = np.bincount(obs.vm_host, weights=c, minlength=n)
        M = np.bincount(obs.vm_host, weights=obs.vm_mig_cost, minlength=n)
        net = obs.p_h * F * urgency(obs.e_ttf, obs.h_days) - M
        ok = (net > 0) & (F > 0)
        m = ok[obs.vm_host]
        if not m.any():
            return np.zeros(0, dtype=np.int64)
        key = obs.rng.uniform(size=int(m.sum()))
        idx = np.lexsort((key, obs.vm_host[m], -net[obs.vm_host[m]]))
        return obs.vm[m][idx]


class Oracle(Policy):
    """P7: knows every host's next failure time and every VM's departure time.

    Candidates: VMs whose host fails within H days, while they would still be running, and whose
    interruption cost exceeds the migration cost. The soonest failures first (a VM whose host
    fails before tomorrow's decision cannot wait); within the same day, by (c - m) per GB. Of
    the engine's two random destination candidates it takes the one that fails later. It is a
    ceiling in practice, not a proof (SIM_SPEC section 12, invariant 9 is checked on seeds).
    """

    name = "P7"
    oracle = True

    def dest_key(self, obs):
        return -obs.truth.host_next_fail  # the candidate that fails last

    def decide(self, obs, budget_gb):
        tr = obs.truth
        tf = tr.host_next_fail[obs.vm_host]
        gain = obs.vm_fail_cost - obs.vm_mig_cost
        m = (tf < obs.day + obs.h_days) & (tr.vm_t_depart > tf) & (gain > 0)
        if not m.any():
            return np.zeros(0, dtype=np.int64)
        fday = np.floor(tf[m])
        idx = np.lexsort((-(gain[m] / obs.vm_mem_gb[m]), fday))
        return obs.vm[m][idx]


class RandomPick(Policy):
    """P8: eligible VMs in random order, until the budget is spent."""

    name = "P8"

    def decide(self, obs, budget_gb):
        return obs.vm[obs.rng.permutation(len(obs.vm))]


def by_name(name: str, **kw) -> Policy:
    return {
        "P0": Never,
        "P1": lambda: Threshold(V1_TAU, "random", "P1"),
        "P2": lambda: Threshold(kw["tau"], kw.get("order", "random"), "P2"),
        "P3": V1Rule,
        "P7": Oracle,
        "P8": RandomPick,
    }[name]()
