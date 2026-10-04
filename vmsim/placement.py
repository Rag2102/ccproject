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


def place_batch(
    mem: np.ndarray,
    tier: np.ndarray,
    free: np.ndarray,
    ok: np.ndarray,
    risk: np.ndarray,
    blend: float,
    rng: np.random.Generator,
    u: np.ndarray | None = None,
) -> np.ndarray:
    """Hosts for one day's arrivals, in arrival order (-1 = rejected: no host has room).

    blend = 0: each VM to a uniformly random host that can take VMs (ok) and has room. With u
    (one pre-drawn uniform per VM, SIM_SPEC section 7) the first choice is host floor(u x n), so
    two runs place a VM on the same host unless that host's state differs between them.
    blend > 0: v1's mechanism on the day's batch (rho_blend): VMs ordered by blend x tier-rank +
    (1 - blend) x U, paired with the free memory of hosts in ascending risk order, so blend = 1
    is adversarial. Overflow is re-drawn uniformly among hosts with room.
    """
    n = len(mem)
    host = np.full(n, -1, dtype=np.int64)
    cand = np.flatnonzero(ok & (free > 0))
    if n == 0 or len(cand) == 0:
        return host
    if blend > 0:
        tie = rng.permutation(n)
        pct = np.empty(n)
        pct[np.lexsort((tie, tier))] = (np.arange(n) + 1) / n
        order = np.argsort(blend * pct + (1 - blend) * rng.uniform(size=n), kind="stable")
        hord = cand[np.lexsort((rng.permutation(len(cand)), risk[cand]))]
        bounds = np.cumsum(free[hord])
        fill = min(1.0, mem.sum() / bounds[-1])
        mid = (np.cumsum(mem[order]) - mem[order] / 2) / fill
        pos = np.minimum(np.searchsorted(bounds, mid), len(hord) - 1)
        host[order] = hord[pos]
    elif u is not None:
        first = np.minimum((u * len(free)).astype(np.int64), len(free) - 1)
        good = ok[first] & (free[first] > 0)
        host[good] = first[good]
        host[~good] = cand[rng.integers(0, len(cand), int((~good).sum()))]
    else:
        host[:] = cand[rng.integers(0, len(cand), n)]
    room = free.astype(float).copy()
    bad = np.zeros(0, dtype=np.int64)
    load = np.bincount(host, weights=mem, minlength=len(free))
    if (load <= room + 1e-9).all():
        return host
    for _ in range(30):
        # on each over-full host keep the VMs (in arrival order) that fit; re-draw the rest
        over = np.flatnonzero(load > room + 1e-9)
        if len(over) == 0:
            bad = np.zeros(0, dtype=np.int64)
            break
        idx = np.flatnonzero(np.isin(host, over))
        o = idx[np.lexsort((idx, host[idx]))]
        h = host[o]
        cum = np.cumsum(mem[o])
        start = np.r_[0, np.flatnonzero(np.diff(h)) + 1]
        base = np.repeat(cum[start] - mem[o][start], np.diff(np.r_[start, len(o)]))
        fits = (cum - base) <= room[h] + 1e-9
        bad = o[~fits]
        np.subtract.at(load, host[bad], mem[bad])
        c2 = cand[room[cand] - load[cand] > 0]
        if len(c2) == 0:
            host[bad] = -1
            break
        host[bad] = c2[rng.integers(0, len(c2), len(bad))]
        np.add.at(load, host[bad], mem[bad])
    if len(bad):  # last resort, one at a time: any host with room, else rejected
        idx = np.flatnonzero(host >= 0)
        idx = idx[~np.isin(idx, bad)]
        left = room - np.bincount(host[idx], weights=mem[idx], minlength=len(free))
        for v in bad:
            r = cand[left[cand] >= mem[v]]
            if len(r):
                j = rng.choice(r)
                host[v], left[j] = j, left[j] - mem[v]
            else:
                host[v] = -1
    return host


def assign_classes(host_risk: np.ndarray, shares) -> np.ndarray:
    """Regime B2: host classes by risk rank, lowest risk first, with the given machine shares."""
    n = len(host_risk)
    order = np.lexsort((np.arange(n), host_risk))
    bounds = np.round(np.cumsum(shares) * n).astype(np.int64)
    cls = np.empty(n, dtype=np.int8)
    cls[order] = np.searchsorted(bounds, np.arange(n), side="right").clip(max=len(shares) - 1)
    return cls


def place_class(
    mem: np.ndarray,
    tier: np.ndarray,
    free: np.ndarray,
    ok: np.ndarray,
    host_class: np.ndarray,
    class_given_tier: np.ndarray,
    rng: np.random.Generator,
    u: np.ndarray,
    v: np.ndarray,
) -> np.ndarray:
    """Regime B2: each VM picks a class from P(class | its tier) with its pre-drawn uniform v,
    then a host inside the class as place_batch does (first choice from u, overflow re-drawn).
    VMs whose class has no room go to any host with room (-1 if none)."""
    cum = np.cumsum(np.asarray(class_given_tier, float)[tier], axis=1)
    cls = (v[:, None] > cum[:, :-1]).sum(1)
    host = np.full(len(mem), -1, dtype=np.int64)
    room = free.astype(float).copy()
    for k in np.unique(cls):
        idx = np.flatnonzero(cls == k)
        hk = np.flatnonzero(host_class == k)
        if len(hk) == 0:
            continue
        z = np.zeros(len(hk))
        loc = place_batch(mem[idx], tier[idx], room[hk], ok[hk], z, 0.0, rng, u[idx])
        good = loc >= 0
        host[idx[good]] = hk[loc[good]]
        np.subtract.at(room, hk[loc[good]], mem[idx[good]])
    left = np.flatnonzero(host < 0)
    if len(left):
        h2 = place_batch(mem[left], tier[left], room, ok, np.zeros(len(room)), 0.0, rng, u[left])
        host[left] = h2
    return host
