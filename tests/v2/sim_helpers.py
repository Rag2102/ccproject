"""Hand-built worlds for the analytic checks (G2 criterion 1): constant hazard, one static VM
per host, no arrivals, no transients, so expected costs have closed forms."""

from __future__ import annotations

import numpy as np

from vmsim import failure, migration
from vmsim.config import CostConfig, SimConfig
from vmsim.engine import Prepared
from vmsim.entities import survival
from vmsim.policies.base import Policy
from vmsim.rng import Streams
from vmsim.worlds import World, n_days


def constant_world(
    n_hosts: int,
    h_daily: float,
    horizon: int = 30,
    seed: int = 1,
    mem_gb: float = 8.0,
    cpu: float = 10.0,
    tier: int = 2,
    sched: np.ndarray | None = None,
    budget_frac: float = 1.0,
) -> Prepared:
    cfg = SimConfig(n_hosts=n_hosts, horizon_days=horizon, warmup_days=0, budget_frac=budget_frac)
    nd = n_days(cfg)
    hz = np.full((n_hosts, nd), h_daily)
    s = Streams(seed)
    fail_t = failure.sample_failure_times(hz, s.gen("failures", 2))
    w = World(
        seed=seed,
        config=cfg.to_dict(),
        drives=np.zeros((n_hosts, 1), dtype=np.int64),
        age0=np.zeros((n_hosts, 1)),
        hazard=hz,
        disk_hazard=hz,
        fail_t=fail_t,
        vm_rows=np.zeros(n_hosts, dtype=np.int64),
        vm_host=np.arange(n_hosts),
        vm_tier=np.full(n_hosts, tier, dtype=np.int8),
        host_risk0=np.full(n_hosts, h_daily),
        vm_age0=np.full(n_hosts, 10.0),
        place_blend=np.array(0.0),
    )
    if sched is None:
        sched = failure.lives(w, cfg.failure, nd, s, new=hz)
        sched = sched[sched["t_fail"] < horizon]
    host_fails = [np.sort(sched["t_fail"][sched["host"] == h]) for h in range(n_hosts)]
    cc, mc = CostConfig(), cfg.migration
    n = n_hosts
    wt = np.full(n, cc.tier_weights[tier])
    dirty = migration.dirty_mbps(np.full(n, cpu), mc)
    dur, blk, _ = migration.precopy(
        np.full(n, mem_gb), dirty, migration.host_bw_mbps(mc) / mc.max_concurrent, mc
    )
    vm = {
        "row": np.zeros(n, dtype=np.int64),
        "mem": np.full(n, mem_gb),
        "tier": np.full(n, tier, dtype=np.int8),
        "w": wt,
        "dirty": dirty,
        "t_arr": np.full(n, -10.0),
        "t_dep": np.full(n, 1e9),
        "fail_cost": wt * cc.d_fail_min,
        "mig_cost_est": migration.migration_cost_min(wt, dur, blk, cc),
        "mig_s_est": dur,
        "host0": np.arange(n),
        "u_place": np.zeros(n),
    }
    return Prepared(
        world=w,
        cfg=cfg,
        streams=s,
        renewed=hz,
        sched=sched,
        host_fails=host_fails,
        vm=vm,
        n_initial=n,
        arr_bounds=np.full(horizon + 1, n),
        dep_order=np.arange(n),
        dep_bounds=np.zeros(horizon + 2, dtype=np.int64),
        transient_n=np.zeros(len(sched), dtype=np.int64),
        transient_cost=np.zeros(len(sched)),
        lam_per_day=0.0,
        surv_grid=survival(np.arange(0, 31, 0.01), cfg.risk_h_days / 2),
    )


def schedule_of(rows: list[tuple[int, float, float]]) -> np.ndarray:
    out = np.zeros(
        len(rows), dtype=[("host", "i8"), ("life", "i8"), ("t_fail", "f8"), ("t_repair", "f8")]
    )
    for i, (h, tf, tr) in enumerate(rows):
        out[i] = (h, 0, tf, tr)
    return np.sort(out, order=["t_fail", "host"])


class MoveOnDay(Policy):
    """Test policy: on one day, every eligible VM (optionally only those on given hosts)."""

    def __init__(self, day: int = 0, hosts=None, name: str = "move"):
        self.day, self.hosts, self.name = day, hosts, name

    def decide(self, obs, budget_gb):
        if obs.day != self.day:
            return np.zeros(0, dtype=np.int64)
        if self.hosts is None:
            return obs.vm
        return obs.vm[np.isin(obs.vm_host, self.hosts)]
