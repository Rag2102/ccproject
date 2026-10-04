"""Live-migration model (plan Week 13; SIM_SPEC section 6).

Pre-copy in rounds, after Clark et al. (2005): round 0 sends all memory, round k re-sends what
was dirtied during round k - 1; stop-and-copy when the remainder is at most `stop_copy_mb` or
after `max_rounds`. A VM whose dirty rate is at least 90% of the bandwidth does not converge and
takes v1's fallback blackout. With `v1_closed_form` the duration is v1's mem / (bw - dirty)
(task 5), so the v1 regression matches v1's costs exactly.

Bandwidth: a host's usable NIC bandwidth is split into `lanes` equal parts, lanes = min(max
concurrent, migrations queued on the host that day); each lane runs its migrations back to back.
"""

from __future__ import annotations

import numpy as np

from vmsim.config import CostConfig, MigrationConfig

MB_PER_GBPS = 125.0  # 1 Gbit/s = 125 MB/s


def host_bw_mbps(mc: MigrationConfig) -> float:
    if mc.v1_closed_form:
        return 1_250.0  # v1 MIGRATION_BANDWIDTH_MBPS, no sharing
    return mc.nic_gbps * mc.usable_share * MB_PER_GBPS


def dirty_mbps(avg_cpu: np.ndarray, mc: MigrationConfig) -> np.ndarray:
    return np.asarray(avg_cpu, float) / 100.0 * mc.dirty_mbps_at_100pct_cpu


def precopy(
    mem_gb: np.ndarray, dirty: np.ndarray, bw: np.ndarray | float, mc: MigrationConfig
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(duration_s, blackout_s, mb_sent) of each migration at bandwidth bw (MB/s).

    duration includes the blackout. For non-converging VMs v1's rule applies: duration =
    blackout = the fallback (v1 sets the pre-copy time to the fallback too).
    """
    mem_mb = np.asarray(mem_gb, float) * 1024
    dirty = np.asarray(dirty, float)
    bw = np.broadcast_to(np.asarray(bw, float), mem_mb.shape)
    conv = dirty < 0.9 * bw
    if mc.v1_closed_form:
        dur = np.where(conv, mem_mb / np.where(conv, bw - dirty, 1.0), mc.blackout_fallback_s)
        blk = np.where(conv, mc.blackout_converged_s, mc.blackout_fallback_s)
        return dur, blk, mem_mb
    remaining = mem_mb.copy()
    t = np.zeros_like(mem_mb)
    sent = np.zeros_like(mem_mb)
    active = conv & (remaining > mc.stop_copy_mb)
    for _ in range(mc.max_rounds):
        if not active.any():
            break
        dt = np.where(active, remaining / bw, 0.0)
        t += dt
        sent += np.where(active, remaining, 0.0)
        remaining = np.where(active, dirty * dt, remaining)
        active &= remaining > mc.stop_copy_mb
    blk = np.maximum(remaining / bw, mc.blackout_converged_s)
    dur = np.where(conv, t + blk, mc.blackout_fallback_s)
    blk = np.where(conv, blk, mc.blackout_fallback_s)
    sent = np.where(conv, sent + remaining, mem_mb)
    return dur, blk, sent


def migration_cost_min(
    tier_w: np.ndarray, duration_s: np.ndarray, blackout_s: np.ndarray, cc: CostConfig
) -> np.ndarray:
    """m = w_tier x blackout (customer minutes) + lambda_bw x duration (resource minutes).

    Under v1_closed_form the duration is v1's pre-copy estimate, so this is v1's
    migration_customer_cost_min + migration_resource_cost_min (task 5).
    """
    return tier_w * blackout_s / 60.0 + cc.lambda_bw * duration_s / 60.0


def schedule(
    src: np.ndarray, mem_gb: np.ndarray, dirty: np.ndarray, t0: float, mc: MigrationConfig
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Start and end time (days) of each migration, in list order per source host.

    Returns (t_start, t_end, duration_s, blackout_s, mb_sent).
    """
    n = len(src)
    if n == 0:
        z = np.zeros(0)
        return z, z, z, z, z
    counts = np.bincount(src)
    lanes = np.minimum(counts[src], 10**9 if mc.v1_closed_form else mc.max_concurrent)
    bw = host_bw_mbps(mc) / (1 if mc.v1_closed_form else lanes)
    dur, blk, sent = precopy(mem_gb, dirty, bw, mc)
    t_start = np.empty(n)
    lane_free: dict[tuple[int, int], float] = {}
    seen: dict[int, int] = {}
    for i in range(n):
        h = int(src[i])
        j = seen.get(h, 0)
        seen[h] = j + 1
        key = (h, j % int(lanes[i]))
        s = lane_free.get(key, t0)
        t_start[i] = s
        lane_free[key] = s + dur[i] / 86_400
    return t_start, t_start + dur / 86_400, dur, blk, sent
