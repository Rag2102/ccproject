"""Initial placement of VMs on hosts, one module per regime (plan Week 11; SIM_SPEC section 8).

Every function returns the host index of each VM and never changes a VM's attributes, except
`trace`, which by design draws each VM's tier given its host's class.

Capacity:
  "slots"  every host takes n_vms // n_hosts VMs (+1 for the first n_vms % n_hosts), as in v1
  "gb"     hosts are filled to the same share of their memory; no host exceeds its capacity
The correlation reported is v1's: tie-corrected Spearman between VM tier and the risk score of
its host, across VMs (scripts/07_correlated_assignment_experiment.py).
"""

from __future__ import annotations

import numpy as np
from scipy.stats import spearmanr

from vmsim.entities import VMs


def achieved_rho(tier: np.ndarray, host_risk: np.ndarray, host: np.ndarray) -> float:
    return float(spearmanr(tier, host_risk[host]).statistic)


def _pair_in_order(
    vm_order: np.ndarray, host_order: np.ndarray, vms: VMs, cap: np.ndarray, capacity: str, rng
):
    """VM k of vm_order goes to the host whose share of the (ordered) capacity it falls in."""
    n_vms, n_hosts = len(vms), len(cap)
    out = np.empty(n_vms, dtype=np.int64)
    if capacity == "slots":
        slots = np.full(n_hosts, n_vms // n_hosts)
        slots[: n_vms % n_hosts] += 1
        out[vm_order] = np.repeat(host_order, slots[host_order])
        return out
    mem = vms.mem_gb[vm_order]
    fill = mem.sum() / cap.sum()
    if fill > 1:
        raise ValueError(f"VMs need {fill:.0%} of cluster memory")
    bounds = np.cumsum(cap[host_order] * fill)
    mid = np.cumsum(mem) - mem / 2  # a VM belongs to the host its midpoint falls in
    pos = np.minimum(np.searchsorted(bounds, mid), n_hosts - 1)
    out[vm_order] = host_order[pos]
    return _repair_capacity(out, vms, cap, rng)


def _repair_capacity(host: np.ndarray, vms: VMs, cap: np.ndarray, rng) -> np.ndarray:
    """Move VMs off any over-full host to random hosts with room: largest VM first among those
    that fit somewhere else (a VM too big to fit anywhere else stays)."""
    used = np.bincount(host, weights=vms.mem_gb, minlength=len(cap))
    for h in np.flatnonzero(used > cap + 1e-9):
        mine = np.flatnonzero(host == h)
        for v in mine[np.argsort(-vms.mem_gb[mine], kind="stable")]:
            if used[h] <= cap[h] + 1e-9:
                break
            room = np.flatnonzero(cap - used >= vms.mem_gb[v])
            room = room[room != h]
            if len(room):
                d = rng.choice(room)
                host[v], used[h], used[d] = d, used[h] - vms.mem_gb[v], used[d] + vms.mem_gb[v]
        if used[h] > cap[h] + 1e-9:
            raise ValueError("no host has room; lower the fill")
    return host


def random(vms: VMs, cap: np.ndarray, rng: np.random.Generator, capacity: str = "gb") -> np.ndarray:
    """Uniform random placement (v1 at rho = 0)."""
    return _pair_in_order(
        rng.permutation(len(vms)), rng.permutation(len(cap)), vms, cap, capacity, rng
    )


def rho_blend(vms: VMs, cap, host_risk, blend: float, rng, capacity: str = "gb") -> np.ndarray:
    """v1's mechanism: score = blend * tier-rank percentile + (1 - blend) * U(0, 1); VMs in score
    order are paired with host capacity in risk order. blend = 0 is random placement."""
    n = len(vms)
    tie = rng.permutation(n)  # v1 ranks ties "first" in file order; here in random order
    rank_pct = np.empty(n)
    rank_pct[np.lexsort((tie, vms.tier))] = (np.arange(n) + 1) / n
    score = blend * rank_pct + (1 - blend) * rng.uniform(size=n)
    host_order = np.lexsort((rng.permutation(len(cap)), host_risk))
    return _pair_in_order(np.argsort(score, kind="stable"), host_order, vms, cap, capacity, rng)


def rho_controlled(
    vms: VMs, cap, host_risk, target: float, rng, capacity: str = "gb", tol: float = 0.005
):
    """Placement whose achieved Spearman(tier, host risk) is within `tol` of `target`.

    Bisection on v1's blend weight with a fixed random draw (the same uniforms at every step), so
    achieved rho is monotone in the blend. Returns (host, blend, achieved).
    """
    state = rng.bit_generator.state
    lo, hi = 0.0, 1.0

    def run(b):
        rng.bit_generator.state = state
        h = rho_blend(vms, cap, host_risk, b, rng, capacity)
        return h, achieved_rho(vms.tier, host_risk, h)

    h_hi, r_hi = run(hi)
    if target > r_hi + tol:
        raise ValueError(f"target rho {target} above the maximum {r_hi:.3f} for these margins")
    h, r = run(lo)
    for _ in range(40):
        if abs(r - target) <= tol:
            break
        mid = (lo + hi) / 2
        h, r = run(mid)
        if r < target:
            lo = mid
        else:
            hi = mid
    return h, (lo + hi) / 2, r


def adversarial(vms: VMs, cap, host_risk, rng, capacity: str = "gb") -> np.ndarray:
    """Critical VMs on the riskiest hosts: VMs by tier and hosts by risk, both highest first."""
    vm_order = np.lexsort((rng.permutation(len(vms)), -vms.tier))
    host_order = np.lexsort((rng.permutation(len(cap)), -host_risk))
    return _pair_in_order(vm_order, host_order, vms, cap, capacity, rng)


def trace(
    vms: VMs, cap, host_class: np.ndarray, tier_given_class: np.ndarray, rng, capacity: str = "gb"
):
    """Random placement, then each VM's tier is drawn from P(tier | its host's class).

    tier_given_class: (n_classes, 3) rows summing to 1, measured in Week 8 (until then the caller
    passes the Azure marginal in every row, which is rho = 0). Returns (host, tier).
    """
    p = np.asarray(tier_given_class, float)
    if not np.allclose(p.sum(1), 1):
        raise ValueError("rows of tier_given_class must sum to 1")
    host = random(vms, cap, rng, capacity)
    cum = np.cumsum(p[host_class[host]], axis=1)
    tier = (rng.uniform(size=len(vms))[:, None] > cum[:, :-1]).sum(1).astype(np.int8)
    return host, tier
