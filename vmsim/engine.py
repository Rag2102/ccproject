"""The simulation engine (plan Week 13; SIM_SPEC sections 2, 4 and 12).

Day-stepped with exact times inside the day. Each daily tick, in this order:
  1. settle migrations that ended before the tick (free their source memory);
  2. departures during the previous day (their memory is freed at this tick, never earlier,
     so capacity is never over-committed);
  3. repairs due by this tick (the host comes back empty, with new drives);
  4. score every host (predictor) and place the day's arrivals (placement regime);
  5. the policy's plan: the engine takes its VMs in order while their GB fit the budget
     (skipping any VM that does not fit and filling the remainder in order), picks each
     destination by power of two choices on p_H and times the migrations (migration.py);
  6. host failures during the day, in time order, each resolved at its exact time against
     arrivals, departures and migrations (a failure at the same instant as a migration's end
     interrupts the VM: SIM_SPEC tie order).
Failures, repairs, arrivals, lifetimes and transient charges are drawn once in `prepare`
from the world's streams, so every policy run on a Prepared sees the same ones (CRN).

Simplifications, stated in SIM_SPEC section 2: VMs shorter than a day are charged as transients
(entities.py); arrivals reserve memory from the tick of their day; migration lanes per host as
in migration.py; a VM migrated away from a host that later fails is safe, and one that arrives on
a host that fails is interrupted there.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from vmsim import failure, migration, placement
from vmsim.accounting import (
    CANCELLED_DEPART,
    CANCELLED_DST,
    DONE,
    DROPPED,
    FAILED_SRC,
    Ledger,
    config_hash,
    git_sha,
)
from vmsim.config import SimConfig, from_dict
from vmsim.entities import MIN_MIGRATE_AGE_DAYS, azure_table, split, survival
from vmsim.policies.base import Feedback, Observation, Policy, Truth
from vmsim.predictor import Miscalibrated, Noisy, RenewalOracle
from vmsim.rng import Streams
from vmsim.worlds import World, n_days

UP, AVOID, DOWN = 0, 1, 2
PENDING, RUNNING, DEPARTED, INTERRUPTED, REJECTED = 0, 1, 2, 3, 4
RUNNING_MIG = -1  # migration status while open
RHO_EVERY_DAYS = 30


@dataclass
class Prepared:
    """Everything random for one world that every policy must share."""

    world: World
    cfg: SimConfig
    streams: Streams
    renewed: np.ndarray
    sched: np.ndarray  # failures in [0, warm-up + horizon), sorted by time
    host_fails: list  # per host: its failure times in order
    vm: dict  # per-VM arrays: initial VMs first, then arrivals in time order
    n_initial: int
    arr_bounds: np.ndarray  # arrivals of day d are vm ids arr_bounds[d]:arr_bounds[d+1]
    dep_order: np.ndarray  # vm ids sorted by departure day
    dep_bounds: np.ndarray
    transient_n: np.ndarray  # per sched row
    transient_cost: np.ndarray
    lam_per_day: float
    surv_grid: np.ndarray


def prepare(world: World, cfg: SimConfig | None = None) -> Prepared:
    cfg = cfg or from_dict(world.config)
    s = Streams(world.seed)
    nd = n_days(cfg)
    t1 = cfg.warmup_days + cfg.horizon_days
    renewed = failure.renewal_hazard(world, cfg.failure, nd)
    sched = failure.lives(world, cfg.failure, nd, s, new=renewed)
    sched = sched[sched["t_fail"] < t1]
    n_hosts = len(world.fail_t)
    order = np.argsort(sched["host"], kind="stable")
    hs = sched["host"][order]
    cuts = np.searchsorted(hs, np.arange(n_hosts + 1))
    tf_sorted = sched["t_fail"][order]
    host_fails = [np.sort(tf_sorted[cuts[h] : cuts[h + 1]]) for h in range(n_hosts)]

    sp = split()
    az = azure_table()
    cap_total = n_hosts * cfg.host_mem_gb
    lam = cfg.placement.init_fill * sp["resident_mem_share"] * cap_total
    lam /= sp["resident_mem_days_mean"]
    g = s.gen("arrivals", 1)
    counts = g.poisson(lam, size=t1)
    t_arr = np.repeat(np.arange(t1), counts) + g.uniform(size=counts.sum())
    o = np.lexsort((np.arange(len(t_arr)), t_arr))
    t_arr = t_arr[o]
    res = sp["resident_rows"]
    rows_new = res[g.integers(0, len(res), len(t_arr))]
    u_place = s.gen("placement", 1).uniform(size=len(t_arr))

    rows = np.concatenate([world.vm_rows, rows_new])
    life = az["lifetime_s"].to_numpy(float)[rows] / 86_400
    t_a = np.concatenate([-world.vm_age0, t_arr])
    mc, cc = cfg.migration, cfg.cost
    tier = az["tier"].to_numpy(np.int8)[rows]
    w = np.asarray(cc.tier_weights)[tier]
    mem = az["memory_gb"].to_numpy(float)[rows]
    cpu = az["avg_cpu"].to_numpy(float)[rows]
    dirty = migration.dirty_mbps(cpu, mc)
    lane_bw = migration.host_bw_mbps(mc) / (1 if mc.v1_closed_form else mc.max_concurrent)
    dur, blk, _ = migration.precopy(mem, dirty, lane_bw, mc)
    vm = {
        "row": rows,
        "mem": mem,
        "tier": tier,
        "w": w,
        "dirty": dirty,
        "t_arr": t_a,
        "t_dep": t_a + life,
        "fail_cost": w * cc.d_fail_min,
        "mig_cost_est": migration.migration_cost_min(w, dur, blk, cc),
        "mig_s_est": dur,
        "host0": np.concatenate([world.vm_host, np.full(len(t_arr), -1)]),
        "u_place": np.concatenate([np.zeros(len(world.vm_rows)), u_place]),
    }
    n0 = len(world.vm_rows)
    arr_day = np.floor(t_arr).astype(np.int64)
    arr_bounds = n0 + np.searchsorted(arr_day, np.arange(t1 + 1))
    dep_day = np.floor(vm["t_dep"]).astype(np.int64)
    dep_order = np.argsort(dep_day, kind="stable")
    dep_bounds = np.searchsorted(dep_day[dep_order], np.arange(t1 + 2))

    # transients present on a host when it fails: Poisson(mean present per host), length-biased
    mu = lam * sp["transients_per_resident"] * sp["transient_life_mean_days"] / n_hosts
    gt = s.gen("failures", 5)
    tn = gt.poisson(mu, size=len(sched))
    trows = sp["transient_rows"]
    tl = az["lifetime_s"].to_numpy(float)[trows]
    pick = trows[gt.choice(len(trows), int(tn.sum()), p=tl / tl.sum())]
    tw = np.asarray(cc.tier_weights)[az["tier"].to_numpy(np.int8)[pick]] * cc.d_fail_min
    tcost = np.bincount(np.repeat(np.arange(len(sched)), tn), weights=tw, minlength=len(sched))
    grid = np.arange(0, 31, 0.01)
    return Prepared(
        world=world,
        cfg=cfg,
        streams=s,
        renewed=renewed,
        sched=sched,
        host_fails=host_fails,
        vm=vm,
        n_initial=n0,
        arr_bounds=arr_bounds,
        dep_order=dep_order,
        dep_bounds=dep_bounds,
        transient_n=tn,
        transient_cost=tcost,
        lam_per_day=float(lam),
        surv_grid=survival(grid, cfg.risk_h_days / 2),
    )


def make_predictor(prep: Prepared, kind: str = "oracle", sigma: float = 0.0, gamma: float = 1.0):
    o = RenewalOracle(prep.world.hazard, prep.renewed, prep.cfg.risk_h_days)
    if kind == "oracle":
        return o
    if kind == "noisy":
        return Noisy(o, sigma, prep.streams)
    if kind == "miscal":
        return Miscalibrated(o, gamma)
    raise ValueError(f"predictor {kind!r} not available yet")


class InvariantError(AssertionError):
    pass


def run(
    prep: Prepared,
    policy: Policy,
    predictor=None,
    budget_frac: float | None = None,
    check: bool = False,
    out_dir: Path | None = None,
    predictor_label: str = "oracle",
) -> dict:
    """One (world, policy) run. Returns the summary; writes outputs if out_dir is given."""
    t_wall = time.perf_counter()
    cfg, V = prep.cfg, prep.vm
    W, T, H = cfg.warmup_days, cfg.horizon_days, cfg.risk_h_days
    t1 = W + T
    n_hosts = len(prep.world.fail_t)
    pred = predictor or make_predictor(prep)
    bfrac = cfg.budget_frac if budget_frac is None else budget_frac
    cap = np.full(n_hosts, float(cfg.host_mem_gb))
    budget = bfrac * cap.sum()
    mc = cfg.migration
    ab = cfg.placement.arrival_blend
    blend = float(prep.world.place_blend) if ab is None else float(ab)

    state = np.full(n_hosts, UP, dtype=np.int8)
    used = np.zeros(n_hosts)
    epoch = np.zeros(n_hosts, dtype=np.int64)
    life_start = np.full(n_hosts, -1, dtype=np.int64)
    repair_day = np.full(n_hosts, np.iinfo(np.int64).max, dtype=np.int64)
    fail_ptr = np.zeros(n_hosts, dtype=np.int64)

    def next_fail(h):
        f = prep.host_fails[h]
        return f[fail_ptr[h]] if fail_ptr[h] < len(f) else np.inf

    host_next_fail = np.array([next_fail(h) for h in range(n_hosts)])

    n_vm = len(V["mem"])
    vm_host = V["host0"].copy()
    vm_state = np.full(n_vm, PENDING, dtype=np.int8)
    vm_mig = np.full(n_vm, -1, dtype=np.int64)
    alive = np.zeros(0, dtype=np.int64)

    M = {k: [] for k in ("vm", "src", "dst", "t_start", "t_end", "gb", "cost", "epoch", "day")}
    M_status: list[int] = []
    M_stop: list[float] = []
    open_ids: list[int] = []
    ledger = Ledger(float(W), float(t1))
    last_t = -np.inf
    sched = prep.sched
    sp = 0
    gb_day: dict[int, float] = {}
    fb_failed: list[int] = []
    fb_icost = np.zeros(n_hosts)
    fb_mcost = np.zeros(n_hosts)
    fb_gb = np.zeros(n_hosts)
    feedback = None

    def close(mid: int, status: int, t: float):
        M_status[mid] = status
        M_stop[mid] = t
        if status == DROPPED:
            gb_day[M["day"][mid]] -= M["gb"][mid]

    def free_src(mid: int):
        s = M["src"][mid]
        if epoch[s] == M["epoch"][mid] and state[s] != DOWN:
            used[s] -= M["gb"][mid]

    for d in range(t1):
        # 1. settle migrations that ended before this tick
        still = []
        for mid in open_ids:
            if M_status[mid] != RUNNING_MIG:
                continue
            if M["t_end"][mid] < d:
                close(mid, DONE, M["t_end"][mid])
                free_src(mid)
                v = M["vm"][mid]
                if vm_mig[v] == mid:
                    vm_mig[v] = -1
            else:
                still.append(mid)
        open_ids = still

        # 2. departures during the previous day
        if d > 0:
            ids = prep.dep_order[prep.dep_bounds[d - 1] : prep.dep_bounds[d]]
            ids = ids[vm_state[ids] == RUNNING]
            for v in ids[vm_mig[ids] >= 0]:  # departed during an open migration
                mid = vm_mig[v]
                td = V["t_dep"][v]
                close(mid, DROPPED if td < M["t_start"][mid] else CANCELLED_DEPART, td)
                free_src(mid)
                vm_mig[v] = -1
            vm_state[ids] = DEPARTED
            ok = state[vm_host[ids]] != DOWN
            np.subtract.at(used, vm_host[ids][ok], V["mem"][ids][ok])
            alive = alive[vm_state[alive] == RUNNING]

        # 3. repairs
        rep = np.flatnonzero((state == DOWN) & (repair_day <= d))
        state[rep] = UP  # also clears an avoid mark
        used[rep] = 0.0
        life_start[rep] = d

        # 4. scores and arrivals (per-day generators: a difference between two runs on one day
        # does not shift the draws of later days)
        rng_arr = prep.streams.gen("placement", 4, d)
        rng_dest = prep.streams.gen("placement", 3, d)
        rng_pol = prep.streams.gen("policy", 0, d)
        sc = pred.score(d, life_start)
        p_h = np.where(state == DOWN, 0.0, sc.p_h)
        if d == 0:
            ini = np.arange(prep.n_initial)
            vm_state[ini] = RUNNING
            np.add.at(used, vm_host[ini], V["mem"][ini])
            alive = ini.copy()
        a0, a1 = prep.arr_bounds[d], prep.arr_bounds[d + 1]
        rejected = 0
        if a1 > a0:
            ids = np.arange(a0, a1)
            hs = placement.place_batch(
                V["mem"][ids],
                V["tier"][ids],
                cap - used,
                state == UP,
                p_h,
                blend,
                rng_arr,
                V["u_place"][ids],
            )
            ok = hs >= 0
            rejected = int((~ok).sum())
            vm_host[ids] = hs
            vm_state[ids[ok]] = RUNNING
            vm_state[ids[~ok]] = REJECTED
            np.add.at(used, hs[ok], V["mem"][ids][ok])
            alive = np.concatenate([alive, ids[ok]])

        # 5. the policy's plan
        el = alive[
            (vm_mig[alive] < 0)
            & (d - V["t_arr"][alive] >= MIN_MIGRATE_AGE_DAYS)
            & (state[vm_host[alive]] != DOWN)
        ]
        age = d - V["t_arr"][el]
        obs = Observation(
            day=d,
            h_days=H,
            p_h=p_h,
            e_ttf=sc.e_ttf,
            host_up=state == UP,
            host_free_gb=cap - used,
            vm=el,
            vm_host=vm_host[el],
            vm_mem_gb=V["mem"][el],
            vm_tier=V["tier"][el],
            vm_age_days=age,
            vm_fail_cost=V["fail_cost"][el],
            vm_survival=prep.surv_grid[np.minimum((age * 100).astype(int), 3099)],
            vm_mig_cost=V["mig_cost_est"][el],
            vm_mig_s=V["mig_s_est"][el],
            rng=rng_pol,
            truth=Truth(host_next_fail, V["t_dep"][el]) if policy.oracle else None,
            feedback=feedback,
            host_avoid=state == AVOID,
            host_life_start=life_start,
        )
        plan = np.asarray(policy.decide(obs, budget), dtype=np.int64) if budget > 0 else []
        # avoid-allocation marks (zero budget means no mitigation action of any kind)
        mark = policy.avoid(obs) if budget > 0 else None
        if mark is not None:
            mark = np.asarray(mark, dtype=bool)
            state[(state == UP) & mark] = AVOID
            state[(state == AVOID) & ~mark] = UP
        if check and len(plan):
            if len(np.unique(plan)) != len(plan) or not np.isin(plan, el).all():
                raise InvariantError(f"day {d}: plan has duplicates or ineligible VMs")
        sel, dsts = [], []
        dkey = policy.dest_key(obs) if len(plan) else p_h
        left = budget
        free = cap - used
        up_hosts = np.flatnonzero(state == UP)
        min_mem = float(V["mem"][plan].min()) if len(plan) else 0.0
        for v in plan:
            if left < min_mem - 1e-9:
                break
            mem = V["mem"][v]
            if mem > left + 1e-9:
                continue  # exact-budget rule: fill the remainder in the policy's order
            src = vm_host[v]
            best = -1
            got = 0
            for _ in range(16):
                j = up_hosts[rng_dest.integers(len(up_hosts))]
                if j != src and free[j] >= mem:
                    if best < 0 or dkey[j] < dkey[best]:
                        best = j
                    got += 1
                    if got == 2:
                        break
            if best < 0:
                continue
            free[best] -= mem
            left -= mem
            sel.append(v)
            dsts.append(best)
        gb_day[d] = budget - left
        if sel:
            sel = np.array(sel)
            dsts = np.array(dsts)
            src = vm_host[sel]
            if check and (state[dsts] != UP).any():
                raise InvariantError(f"day {d}: migration to a host that is not up")
            ts, te, dur, blk, _ = migration.schedule(
                src, V["mem"][sel], V["dirty"][sel], float(d), mc
            )
            cost = migration.migration_cost_min(V["w"][sel], dur, blk, cfg.cost)
            np.add.at(fb_mcost, src, cost)
            np.add.at(fb_gb, src, V["mem"][sel])
            base = len(M_status)
            for k, col in (
                ("vm", sel),
                ("src", src),
                ("dst", dsts),
                ("t_start", ts),
                ("t_end", te),
                ("gb", V["mem"][sel]),
                ("cost", cost),
                ("epoch", epoch[src]),
                ("day", np.full(len(sel), d)),
            ):
                M[k].extend(col.tolist())
            M_status.extend([RUNNING_MIG] * len(sel))
            M_stop.extend([np.nan] * len(sel))
            ids = np.arange(base, base + len(sel))
            open_ids.extend(ids.tolist())
            vm_mig[sel] = ids
            vm_host[sel] = dsts
            np.add.at(used, dsts, V["mem"][sel])

        # 6. failures during the day
        while sp < len(sched) and sched["t_fail"][sp] < d + 1:
            h, tf = int(sched["host"][sp]), float(sched["t_fail"][sp])
            if check:
                if tf < last_t:
                    raise InvariantError("time went backwards")
                if state[h] == DOWN:
                    raise InvariantError(f"host {h} failed while down")
            last_t = tf
            n_it = len(ledger.interrupts)
            _fail(
                h,
                tf,
                V,
                vm_host,
                vm_state,
                vm_mig,
                alive,
                M,
                M_status,
                open_ids,
                close,
                free_src,
                used,
                state,
                cap,
                rng_arr,
                ledger,
            )
            ledger.transient(tf, h, prep.transient_n[sp], prep.transient_cost[sp])
            fb_failed.append(h)
            fb_icost[h] += prep.transient_cost[sp] + sum(r[4] for r in ledger.interrupts[n_it:])
            state[h] = DOWN
            used[h] = 0.0
            epoch[h] += 1
            repair_day[h] = int(np.ceil(sched["t_repair"][sp]))
            fail_ptr[h] += 1
            host_next_fail[h] = next_fail(h)
            sp += 1
        alive = alive[vm_state[alive] == RUNNING]
        feedback = Feedback(np.array(fb_failed, dtype=np.int64), fb_icost, fb_mcost, fb_gb)
        fb_failed, fb_icost, fb_mcost = [], np.zeros(n_hosts), np.zeros(n_hosts)
        fb_gb = np.zeros(n_hosts)

        rho = np.nan
        if d % RHO_EVERY_DAYS == 0 and len(alive) > 10:
            on = alive[state[vm_host[alive]] != DOWN]
            x, y = V["tier"][on], p_h[vm_host[on]]
            if x.min() < x.max() and y.min() < y.max():
                rho = float(spearmanr(x, y).statistic)
        ledger.daily.append(
            {
                "day": d,
                "budget_gb": budget,
                "gb_planned": budget - left,
                "n_planned": len(sel),
                "rejected": rejected,
                "hosts_down": int((state == DOWN).sum()),
                "vms_running": int(len(alive)),
                "mem_used_share": float(used.sum() / cap.sum()),
                "rho_tier_risk": rho,
            }
        )
        if check:
            _check(
                d, V, vm_host, vm_state, used, cap, state, M, M_status, epoch, prep, budget, left
            )

    for mid in open_ids:  # migrations still open at the end
        if M_status[mid] == RUNNING_MIG:
            close(mid, DONE, M["t_end"][mid])

    ledger.migrations = {
        **{k: np.asarray(v) for k, v in M.items() if k not in ("epoch",)},
        "status": np.asarray(M_status, dtype=np.int64),
        "t_stop": np.asarray(M_stop),
    }
    mg_extra = None
    if len(M_status):
        vm_ids = np.asarray(M["vm"])
        srcs = np.asarray(M["src"])
        tstart = np.asarray(M["t_start"])
        nxt = np.array(
            [
                f[np.searchsorted(f, t)] if np.searchsorted(f, t) < len(f) else np.inf
                for f, t in zip((prep.host_fails[s] for s in srcs), tstart, strict=True)
            ]
        )
        mg_extra = pd.DataFrame(
            {
                "src_next_fail": nxt,
                "necessary": (nxt - tstart <= H) & (V["t_dep"][vm_ids] > nxt),
                "tier": V["tier"][vm_ids],
            }
        )
    for r in ledger.daily:
        r["gb_started"] = gb_day.get(r["day"], 0.0)
    summary, mg = ledger.summarise(mg_extra)
    it, tr, _ = ledger.tables()
    h = hashlib.sha256()
    for t in (it, tr, mg):
        h.update(pd.util.hash_pandas_object(t, index=False).to_numpy().tobytes())
        h.update(",".join(map(str, t.columns)).encode())
    meta = {
        "seed": prep.world.seed,
        "policy": policy.name,
        "predictor": predictor_label,
        "budget_frac": bfrac,
        "config_hash": config_hash(cfg.to_dict()),
        "git_sha": git_sha() if out_dir else "",
        "n_hosts": n_hosts,
        "horizon_days": T,
        "warmup_days": W,
        "vms_total": int(n_vm),
        "outcomes_sha256": h.hexdigest(),
        "wall_s": round(time.perf_counter() - t_wall, 3),
        "rho_tier_risk_mean": _nanmean([r["rho_tier_risk"] for r in ledger.daily]),
        "rho_tier_risk_horizon": _nanmean(
            [r["rho_tier_risk"] for r in ledger.daily if r["day"] >= W]
        ),
    }
    if out_dir is not None:
        ledger.write(Path(out_dir), meta, summary, mg)
    return {**meta, **summary}


def _nanmean(x) -> float:
    x = np.asarray(x, float)
    return float(np.mean(x[~np.isnan(x)])) if (~np.isnan(x)).any() else float("nan")


def _fail(
    h,
    tf,
    V,
    vm_host,
    vm_state,
    vm_mig,
    alive,
    M,
    M_status,
    open_ids,
    close,
    free_src,
    used,
    state,
    cap,
    rng,
    ledger,
):
    """Resolve host h failing at time tf (SIM_SPEC section 4, HOST_FAIL)."""
    on = alive[(vm_host[alive] == h) & (vm_state[alive] == RUNNING)]
    for v in on:
        mid = vm_mig[v]
        if V["t_dep"][v] <= tf:  # gone before the failure
            vm_state[v] = DEPARTED
            if mid >= 0 and M["dst"][mid] == h:
                ts, te = M["t_start"][mid], M["t_end"][mid]
                td = V["t_dep"][v]
                close(mid, DROPPED if td < ts else (CANCELLED_DEPART if td <= te else DONE), td)
                free_src(mid)
                vm_mig[v] = -1
            continue
        if V["t_arr"][v] > tf:  # arrives later today: place it elsewhere
            ok = np.flatnonzero((state == UP) & (cap - used >= V["mem"][v]))
            ok = ok[ok != h]
            if len(ok):
                j = rng.choice(ok)
                vm_host[v] = j
                used[j] += V["mem"][v]
            else:
                vm_state[v] = REJECTED
            continue
        if mid >= 0 and M["dst"][mid] == h:  # migrating onto the failing host
            ts, te = M["t_start"][mid], M["t_end"][mid]
            if tf < ts or tf <= te:
                close(mid, DROPPED if tf < ts else CANCELLED_DST, tf)
                vm_host[v] = M["src"][mid]
                vm_mig[v] = -1
                continue
            close(mid, DONE, te)  # it had arrived: interrupted below
            free_src(mid)
            vm_mig[v] = -1
        vm_state[v] = INTERRUPTED
        ledger.interrupt(tf, v, h, V["tier"][v], V["fail_cost"][v])
    for mid in open_ids:  # migrations out of the failing host
        if M_status[mid] != RUNNING_MIG or M["src"][mid] != h:
            continue
        v = M["vm"][mid]
        if vm_state[v] != RUNNING or vm_mig[v] != mid or V["t_dep"][v] <= tf:
            continue
        ts, te = M["t_start"][mid], M["t_end"][mid]
        if te < tf:  # finished before the failure: safe
            close(mid, DONE, te)
            vm_mig[v] = -1
            continue
        dst = M["dst"][mid]
        if state[dst] != DOWN:
            used[dst] -= M["gb"][mid]
        close(mid, DROPPED if tf < ts else FAILED_SRC, tf)
        vm_mig[v] = -1
        vm_host[v] = h
        vm_state[v] = INTERRUPTED
        ledger.interrupt(tf, v, h, V["tier"][v], V["fail_cost"][v], in_flight=tf >= ts)


def _check(d, V, vm_host, vm_state, used, cap, state, M, M_status, epoch, prep, budget, left):
    """SIM_SPEC section 12, invariants 1, 2 and 6, after every day."""
    arrived = prep.arr_bounds[d + 1]
    if (vm_state[:arrived] == PENDING).any() or (vm_state[arrived:] != PENDING).any():
        raise InvariantError(f"day {d}: VM conservation")
    run_ = np.flatnonzero(vm_state == RUNNING)
    expect = np.bincount(vm_host[run_], weights=V["mem"][run_], minlength=len(cap))
    # an open migration still holds the VM's memory on its source
    for mid, st in enumerate(M_status):
        if st == RUNNING_MIG:
            s = M["src"][mid]
            if epoch[s] == M["epoch"][mid] and state[s] != DOWN:
                expect[s] += M["gb"][mid]
    if (state[vm_host[run_]] == DOWN).any():
        raise InvariantError(f"day {d}: a running VM is on a down host")
    if np.abs(used - expect).max() > 1e-6:
        raise InvariantError(f"day {d}: memory accounting differs from the VMs present")
    if (used > cap + 1e-6).any():
        raise InvariantError(f"day {d}: capacity exceeded on {np.flatnonzero(used > cap + 1e-6)}")
    if budget - left > budget + 1e-9 or left < -1e-9:
        raise InvariantError(f"day {d}: budget exceeded")
