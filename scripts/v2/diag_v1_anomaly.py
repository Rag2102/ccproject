"""Week 3 diagnostics: why the threshold beat the cost-sensitive policy at rho = 0 in v1.

Rebuilds the v1 replay world from the same inputs (Backblaze hosts, the hazard/TTF lookup,
Azure VMs assigned to hosts with seed 42) and tests hypotheses H1-H8 of docs/v2/v1_anomaly.md.

In v1 a policy decides per host, and every score it uses is increasing in the host's 30-day
failure probability p: score_h(t) = a_h * p(t) + b_h. A host is migrated at the first 30-day
bin where its score crosses the policy's line, before its real failure or end of observation.
So one harness compares any two policies at an exactly matched budget (number of hosts, or GB
of VM memory moved):

    threshold (P1/P2)   a = 1          b = 0
    v1 cost-sensitive   a = F / M      b = 0           (urgency is 1 everywhere, see H2)
    BAM, count budget   a = F          b = -M          (expected benefit p*F - M)
    BAM, GB budget      a = F / GB     b = -M / GB     (benefit per GB)

F = sum of the host's VM failure costs, M = sum of its VM migration costs (customer-minutes).
Delta follows the v5 metric: (C_ref - C_policy) / C_ref, positive when the policy is better.

Verdict rules (VERDICT_RULES) were written before the first run of this script.

Run from the repository root:  .venv/bin/python scripts/v2/diag_v1_anomaly.py
Writes results/summary/v1_anomaly.json and results/figures/v1_anomaly_*.pdf.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
OUT_JSON = ROOT / "results" / "summary" / "v1_anomaly.json"
FIG_DIR = ROOT / "results" / "figures"

V1_SEED = 42
DEV_SEEDS = list(range(101, 111))  # v5 seed family "dev"; pilot and eval seeds are not touched
BIN_DAYS = 30
SIGMAS = [0.0, 0.25, 0.5, 1.0, 1.5, 2.0]
WINDOWS = [7, 30, 90, 365, float("inf")]
OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442"]

VERDICT_RULES = {
    "H1": "confirmed if overall observed/expected failures is outside [0.90, 1.10] or at least two "
    "p-deciles have |z| > 3; rejected if overall is within [0.95, 1.05] and no decile has |z| > 3; "
    "else inconclusive",
    "H2": "rejected if urgency exceeds 1 in no row of the lookup table (urgency is identically 1); "
    "confirmed if setting urgency to 1 moves Delta by at least 1 point",
    "H3": "confirmed if matching the budget in GB moves Delta to -1% or above (materiality); "
    "rejected if Delta stays at or below -2%; else inconclusive",
    "H4": "confirmed if any reweighting of the Unknown class moves Delta by at least 1 point; "
    "rejected if every variant moves it by less than 0.5 point; else inconclusive",
    "H5": "rejected if, with calibrated oracle p (synthetic fates, sigma = 0), the v1 rule still "
    "loses by 1% or more on average; confirmed if it does not lose at sigma = 0 and loses at a "
    "sigma of 1 or less; else inconclusive",
    "H6": "confirmed if any accounting window moves Delta by at least 1 point or flips its sign; "
    "else rejected",
    "H7": "confirmed if BAM with the denominator matching the budget reaches Delta >= -1% at both "
    "budgets in the v1 world and on average over the dev seeds; rejected if it stays at or below "
    "-2%; else inconclusive",
    "H8": "rejected if the three within-host orders change total cost by less than 0.1%",
}


# ---------------------------------------------------------------------------------------------
# World
# ---------------------------------------------------------------------------------------------
@dataclass
class Group:
    starts: np.ndarray  # (B,) bin start days, ascending
    p: np.ndarray  # (B,) 30-day failure probability used by the policies
    cummax: np.ndarray  # (B,) running maximum of p
    hazard: np.ndarray  # (B,) per-bin hazard, used for synthetic fates


@dataclass
class World:
    gid: np.ndarray  # (H,) group index
    cutoff: np.ndarray  # (H,) age at failure or end of observation, days
    failed: np.ndarray  # (H,) bool
    F: np.ndarray
    M: np.ndarray
    GB: np.ndarray
    n_valid: np.ndarray  # bins with start < cutoff
    pmax: np.ndarray  # max p over valid bins
    tier: np.ndarray  # most common criticality tier among the host's VMs
    shift: np.ndarray | None = None  # per-host log-odds noise the policies see (H5 only)


def load_inputs():
    drv = pd.read_csv(PROC / "backblaze_drives_clean.csv")
    drv = drv.dropna(subset=["age_days"]).reset_index(drop=True)
    lut = pd.read_csv(PROC / "ttf_lookup_table.csv")
    top = sorted(lut.loc[lut["model_grp"] != "OTHER", "model_grp"].unique())
    drv["model_grp"] = np.where(drv["model"].isin(top), drv["model"], "OTHER")
    names = sorted(drv["model_grp"].unique())
    groups = []
    for g in names:
        b = lut[lut["model_grp"] == g].sort_values("bin_start_days")
        p = b["p_fail_within_window"].to_numpy(float)
        groups.append(
            Group(
                b["bin_start_days"].to_numpy(float),
                p,
                np.maximum.accumulate(p),
                b["hazard_30d"].to_numpy(float),
            )
        )
    gid = pd.Categorical(drv["model_grp"], categories=names).codes.astype(int)
    cols = [
        "criticality_tier",
        "memory_gb",
        "failure_customer_cost_min",
        "migration_customer_cost_min",
        "migration_resource_cost_min",
    ]
    vm = pd.read_csv(PROC / "azure_vms_with_costs.csv.gz", usecols=cols)
    return drv, gid, groups, lut, vm


def assign(n_vms: int, n_hosts: int, seed: int) -> np.ndarray:
    """v1's assignment: uniform at random, one draw per VM, in file order."""
    return np.random.default_rng(seed).integers(0, n_hosts, size=n_vms)


def valid_and_pmax(groups, gid, cutoff):
    n_valid = np.zeros(len(gid), int)
    pmax = np.full(len(gid), -np.inf)
    for k, g in enumerate(groups):
        idx = np.flatnonzero(gid == k)
        nv = np.searchsorted(g.starts, cutoff[idx], side="left")
        n_valid[idx] = nv
        ok = nv > 0
        pmax[idx[ok]] = g.cummax[nv[ok] - 1]
    return n_valid, pmax


def build_world(drv, gid, groups, vm, host_of_vm, unknown_factor=1.0, drop_unknown=False):
    fail_vm = vm["failure_customer_cost_min"].to_numpy(float).copy()
    mig_cust = vm["migration_customer_cost_min"].to_numpy(float).copy()
    mig_res = vm["migration_resource_cost_min"].to_numpy(float)
    gb = vm["memory_gb"].to_numpy(float)
    # The Azure trace spells this label "Unkown"; v1 maps it to the medium tier.
    unknown = (vm["criticality_tier"] == "medium").to_numpy()
    keep = ~unknown if drop_unknown else np.ones(len(vm), bool)
    # Both customer-facing costs carry the criticality weight in v1 (task 5), so a new weight
    # for Unknown scales both; the resource part of the migration cost does not.
    fail_vm[unknown] *= unknown_factor
    mig_cust[unknown] *= unknown_factor
    n = len(drv)
    h = host_of_vm[keep]
    F = np.bincount(h, weights=fail_vm[keep], minlength=n)
    M = np.bincount(h, weights=(mig_res + mig_cust)[keep], minlength=n)
    GB = np.bincount(h, weights=gb[keep], minlength=n)
    tiers = vm["criticality_tier"].to_numpy()[keep]
    counts = np.stack([np.bincount(h[tiers == t], minlength=n) for t in ("low", "medium", "high")])
    tier = np.array(["low", "medium", "high"])[counts.argmax(axis=0)]
    cutoff = drv["age_days"].to_numpy(float)
    n_valid, pmax = valid_and_pmax(groups, gid, cutoff)
    return World(gid, cutoff, drv["failed"].to_numpy(int) == 1, F, M, GB, n_valid, pmax, tier)


# ---------------------------------------------------------------------------------------------
# Policies, selection, accounting
# ---------------------------------------------------------------------------------------------
def coeffs(w: World, policy: str):
    one = np.ones_like(w.F)
    with np.errstate(divide="ignore", invalid="ignore"):
        table = {
            "threshold": (one, 0 * one),
            "v1_cost_sensitive": (w.F / w.M, 0 * one),
            "bam_count": (w.F, -w.M),
            "bam_gb": (w.F / w.GB, -w.M / w.GB),
        }
    a, b = table[policy]
    bad = ~np.isfinite(a) | ~np.isfinite(b)
    return np.where(bad, 0.0, a), np.where(bad, -np.inf, b)


def select_line(w: World, policy: str, theta: float):
    """Threshold semantics as in v1: migrate when the score first exceeds theta (strict)."""
    a, b = coeffs(w, policy)
    return a * w.pmax + b > theta


def select_budget(
    w: World, policy: str, kind: str, amount: float, tie_seed: int, positive_only: bool = False
):
    """Spend an exact budget on the highest scores; ties broken by a fixed random order."""
    a, b = coeffs(w, policy)
    score = a * w.pmax + b
    tie = np.random.default_rng(tie_seed).random(len(score))
    order = np.lexsort((tie, -score))
    if positive_only:
        order = order[score[order] > 0]
    sel = np.zeros(len(score), bool)
    if kind == "count":
        sel[order[: int(amount)]] = True
    else:
        take = np.cumsum(w.GB[order]) <= amount + 1e-9
        sel[order[take]] = True
    return sel


def migration_times(w: World, groups, policy: str, sel: np.ndarray, line: float | None = None):
    """Day of the first bin at which each selected host's score reaches the selection line.

    With line=None the line is the lowest selected score (budget semantics, >=); otherwise
    the strict v1 threshold semantics apply."""
    a, b = coeffs(w, policy)
    score = a * w.pmax + b
    strict = line is not None
    if line is None:
        line = score[sel].min() if sel.any() else np.inf
    t = np.full(len(sel), np.nan)
    for k, g in enumerate(groups):
        idx = np.flatnonzero(sel & (w.gid == k))
        if idx.size == 0:
            continue
        with np.errstate(divide="ignore", invalid="ignore"):
            p_star = (line - b[idx]) / a[idx]
        if not strict:
            p_star = p_star * (1 - 1e-12)  # the boundary host must cross at its own peak bin
        if w.shift is not None:  # the policy saw noisy p: map its line back to the true curve
            q = np.clip(p_star, 1e-15, 1 - 1e-15)
            p_star = 1 / (1 + np.exp(-(np.log(q / (1 - q)) - w.shift[idx])))
        j = np.searchsorted(g.cummax, p_star, side="right" if strict else "left")
        j = np.minimum(j, w.n_valid[idx] - 1)
        t[idx] = g.starts[j]
    return t


def total_cost(w: World, sel: np.ndarray, t_mig=None, window: float = float("inf")) -> float:
    protected = sel & w.failed
    if np.isfinite(window):
        protected &= (w.cutoff - t_mig) <= window
    return float(w.M[sel].sum() + w.F[w.failed & ~protected].sum())


def delta(cost_policy: float, cost_ref: float) -> float:
    return (cost_ref - cost_policy) / cost_ref


def v1_matched_tau(w: World, target: int, lo: float, hi: float) -> float:
    """v1's bisection (25 steps) and its rule of keeping whichever bound lands closer."""
    for _ in range(25):
        mid = (lo + hi) / 2
        if (w.pmax > mid).sum() > target:
            lo = mid
        else:
            hi = mid
    n_lo, n_hi = (w.pmax > lo).sum(), (w.pmax > hi).sum()
    return lo if abs(n_lo - target) <= abs(n_hi - target) else hi


# ---------------------------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------------------------
def reproduce_v1(w, lut):
    cs = select_line(w, "v1_cost_sensitive", 1.0)
    tau = float(lut["p_fail_within_window"].quantile(0.95))
    naive = w.pmax > tau
    tau_m = v1_matched_tau(w, int(cs.sum()), tau, float(lut["p_fail_within_window"].max()))
    matched = w.pmax > tau_m
    out = {
        "cost_sensitive": {
            "hosts": int(cs.sum()),
            "cost": total_cost(w, cs),
            "gb": float(w.GB[cs].sum()),
        },
        "threshold_naive": {"tau": tau, "hosts": int(naive.sum()), "cost": total_cost(w, naive)},
        "threshold_matched_v1": {
            "tau": tau_m,
            "hosts": int(matched.sum()),
            "cost": total_cost(w, matched),
            "gb": float(w.GB[matched].sum()),
        },
    }
    out["delta_v1"] = delta(out["cost_sensitive"]["cost"], out["threshold_matched_v1"]["cost"])
    assert abs(out["cost_sensitive"]["cost"] - 456532.7306) < 0.01, out
    assert abs(out["threshold_naive"]["cost"] - 410866.9488) < 0.01, out
    assert abs(out["threshold_matched_v1"]["cost"] - 442700.7434) < 0.01, out
    return out, cs, matched, tau_m


MULTS = [0.5, 1.0, 2.0]
GRID_WINDOWS = [30.0, float("inf")]
RANKERS = {
    "count": ["v1_cost_sensitive", "bam_count"],
    "gb": ["v1_cost_sensitive", "bam_count", "bam_gb"],
}


def budget_grid(w, groups, cs, seed):
    """Every ranking against the threshold at the same exact budget.

    Budgets are multiples of the v1 rule's own operating point (its number of hosts, or its GB).
    At 1x, BAM and the v1 rule select the same hosts: the v1 rule p*F > M is exactly "positive
    BAM benefit", so ranking differences only show at 0.5x and 2x. BAM stops when the benefit is
    no longer positive (it may leave budget unspent); the v1 score and the threshold do not.
    Each cell is reported under two accountings: a migration averts a failure at any later time
    (v1) or only within 30 days, the horizon of the p the policies use."""
    base = {"count": float(cs.sum()), "gb": float(w.GB[cs].sum())}
    out = {}
    for kind, amount0 in base.items():
        for mult in MULTS:
            amount = amount0 * mult
            sel_thr = select_budget(w, "threshold", kind, amount, seed)
            t_thr = migration_times(w, groups, "threshold", sel_thr)
            for pol in RANKERS[kind]:
                pos = pol.startswith("bam")
                sel = select_budget(w, pol, kind, amount, seed, positive_only=pos)
                t = migration_times(w, groups, pol, sel)
                for win in GRID_WINDOWS:
                    key = f"{kind}|{mult}|{pol}|{'inf' if not np.isfinite(win) else int(win)}"
                    out[key] = {
                        "delta": delta(
                            total_cost(w, sel, t, win), total_cost(w, sel_thr, t_thr, win)
                        ),
                        "hosts": int(sel.sum()),
                        "gb": float(w.GB[sel].sum()),
                        "threshold_hosts": int(sel_thr.sum()),
                    }
    return out


def h1_calibration(w: World, groups):
    rows = []
    for k, g in enumerate(groups):
        idx = np.flatnonzero(w.gid == k)
        nv = w.n_valid[idx]
        B = len(g.starts)
        at_risk = np.bincount(nv, minlength=B + 1)[::-1].cumsum()[::-1][1 : B + 1]
        fail_bin = nv[w.failed[idx] & (nv > 0)] - 1
        fails = np.bincount(fail_bin, minlength=B)
        for j in range(B):
            if at_risk[j]:
                rows.append((g.p[j], at_risk[j], fails[j]))
    cells = pd.DataFrame(rows, columns=["p", "n", "y"]).sort_values("p")
    cells["expected"] = cells["p"] * cells["n"]
    w_cum = cells["n"].cumsum() / cells["n"].sum()
    cells["decile"] = np.minimum((w_cum * 10).astype(int), 9)
    dec = cells.groupby("decile").agg(
        n=("n", "sum"), observed=("y", "sum"), expected=("expected", "sum")
    )
    dec["mean_p"] = dec["expected"] / dec["n"]
    dec["obs_rate"] = dec["observed"] / dec["n"]
    dec["z"] = (dec["observed"] - dec["expected"]) / np.sqrt(dec["expected"])
    overall = float(cells["y"].sum() / cells["expected"].sum())
    n_z3 = int((dec["z"].abs() > 3).sum())
    if overall < 0.90 or overall > 1.10 or n_z3 >= 2:
        verdict = "confirmed"
    elif 0.95 <= overall <= 1.05 and n_z3 == 0:
        verdict = "rejected"
    else:
        verdict = "inconclusive"
    return {
        "observed_over_expected": overall,
        "deciles": dec.reset_index().to_dict("records"),
        "deciles_abs_z_gt_3": n_z3,
        "verdict": verdict,
        "note": "in-sample: the hazard model was trained on 80% of these drives",
    }, dec


def per_tier_calibration(w: World, groups):
    out = {}
    exp_host = np.zeros(len(w.gid))
    for k, g in enumerate(groups):
        idx = np.flatnonzero(w.gid == k)
        csum = np.concatenate([[0.0], np.cumsum(g.p)])
        exp_host[idx] = csum[w.n_valid[idx]]
    for t in ("low", "medium", "high"):
        m = w.tier == t
        out[t] = {
            "hosts": int(m.sum()),
            "observed": int(w.failed[m].sum()),
            "expected": float(exp_host[m].sum()),
            "observed_over_expected": float(w.failed[m].sum() / exp_host[m].sum()),
        }
    return out


def h2_urgency(lut, w, cs_cost):
    u = np.clip(30.0 / np.maximum(lut["expected_ttf_days"].to_numpy(float), 1.0), 1.0, 5.0)
    share = float((u > 1).mean())
    return {
        "share_of_lookup_rows_with_urgency_above_1": share,
        "min_expected_ttf_days": float(lut["expected_ttf_days"].min()),
        "verdict": "rejected" if share == 0 else "inconclusive",
        "note": "urgency is identically 1, so the v1 rule is p * F > M; cost with urgency "
        f"removed equals the v1 cost ({cs_cost:,.1f})",
    }


def h4_unknown(drv, gid, groups, vm, host_of_vm, seed):
    variants = {
        "v1 (Unknown weight 0.6)": (1.0, False),
        "Unknown as low (0.3)": (0.5, False),
        "Unknown as high (1.0)": (1.0 / 0.6, False),
        "Unknown VMs removed": (1.0, True),
    }
    out = {}
    for name, (factor, drop) in variants.items():
        w = build_world(drv, gid, groups, vm, host_of_vm, factor, drop)
        cs = select_line(w, "v1_cost_sensitive", 1.0)
        thr = select_budget(w, "threshold", "count", int(cs.sum()), seed)
        ratio = np.log(w.F[w.M > 0] / w.M[w.M > 0])
        cs_fix = select_budget(w, "v1_cost_sensitive", "count", 5116, seed)
        thr_fix = select_budget(w, "threshold", "count", 5116, seed)
        out[name] = {
            "delta_cs_vs_threshold_exact_count": delta(total_cost(w, cs), total_cost(w, thr)),
            "delta_at_fixed_5116_hosts": delta(total_cost(w, cs_fix), total_cost(w, thr_fix)),
            "hosts": int(cs.sum()),
            "sd_log_F_over_M": float(ratio.std()),
        }

    def rule(key):
        base = out["v1 (Unknown weight 0.6)"][key]
        moves = [abs(v[key] - base) for v in out.values()]
        verdict = (
            "confirmed"
            if max(moves) >= 0.01
            else "rejected"
            if max(moves) < 0.005
            else "inconclusive"
        )
        return 100 * max(moves), verdict

    pre_move, pre_verdict = rule("delta_cs_vs_threshold_exact_count")
    fix_move, fix_verdict = rule("delta_at_fixed_5116_hosts")
    return {
        "variants": out,
        "pre_written_rule_max_move_points": pre_move,
        "pre_written_rule_verdict": pre_verdict,
        "fixed_budget_max_move_points": fix_move,
        "verdict": fix_verdict,
        "note": "the pre-written test let the operating point move with the weight (4,010 to "
        "6,216 hosts); the verdict uses the fixed-budget control, a deviation decided "
        "after the first run",
    }


def synthetic_world(w: World, groups, seed: int) -> World:
    """Same hosts, VMs and observation ends; failures drawn from the model's own hazard, so
    p is calibrated by construction."""
    rng = np.random.default_rng(seed)
    obs_end = w.cutoff.copy()
    fail_age = np.full(len(obs_end), np.inf)
    for k, g in enumerate(groups):
        idx = np.flatnonzero(w.gid == k)
        surv = np.cumprod(1.0 - g.hazard)
        u = rng.random(idx.size)
        j = np.searchsorted(-surv, -u, side="right")  # first bin where survival drops below u
        hit = j < len(surv)
        fail_age[idx[hit]] = g.starts[j[hit]] + BIN_DAYS * rng.random(hit.sum())
    failed = fail_age < obs_end
    cutoff = np.where(failed, fail_age, obs_end)
    n_valid, pmax = valid_and_pmax(groups, w.gid, cutoff)
    return World(w.gid, cutoff, failed, w.F, w.M, w.GB, n_valid, pmax, w.tier)


def h5_noise(w: World, groups):
    runs = {(s, win): [] for s in SIGMAS for win in GRID_WINDOWS}
    for seed in DEV_SEEDS:
        sw = synthetic_world(w, groups, seed)
        eps = np.random.default_rng(seed + 1000).standard_normal(len(sw.pmax))
        logit = np.log(sw.pmax / (1 - sw.pmax))
        for s in SIGMAS:
            if s == 0:
                nw = sw
            else:
                nw = World(
                    sw.gid,
                    sw.cutoff,
                    sw.failed,
                    sw.F,
                    sw.M,
                    sw.GB,
                    sw.n_valid,
                    1 / (1 + np.exp(-(logit + s * eps))),
                    sw.tier,
                    s * eps,
                )
            cs = select_line(nw, "v1_cost_sensitive", 1.0)
            t_cs = migration_times(nw, groups, "v1_cost_sensitive", cs, line=1.0)
            thr = select_budget(nw, "threshold", "count", int(cs.sum()), seed)
            t_thr = migration_times(nw, groups, "threshold", thr)
            for win in GRID_WINDOWS:
                runs[(s, win)].append(
                    delta(total_cost(nw, cs, t_cs, win), total_cost(nw, thr, t_thr, win))
                )
    summary = {}
    for (s, win), v in runs.items():
        key = "inf" if not np.isfinite(win) else str(int(win))
        summary.setdefault(key, {})[str(s)] = {
            "mean": float(np.mean(v)),
            "sd": float(np.std(v)),
            "min": float(np.min(v)),
            "max": float(np.max(v)),
        }
    m0 = summary["inf"]["0.0"]["mean"]
    small = [summary["inf"][str(s)]["mean"] for s in SIGMAS if 0 < s <= 1.0]
    if m0 <= -0.01:
        verdict = "rejected"
    elif min(small) < 0:
        verdict = "confirmed"
    else:
        verdict = "inconclusive"
    return {
        "sigmas": SIGMAS,
        "delta_by_window_then_sigma": summary,
        "seeds": DEV_SEEDS,
        "verdict": verdict,
        "note": "fates drawn from hazard_30d, so p is calibrated by construction; persistent "
        "per-host log-odds noise shared by both policies; observation ends from the "
        "real data; v1 rule at its own operating point vs threshold at the same "
        "count",
    }, runs


def h6_windows(w, groups, cs, matched, tau_m):
    t_cs = migration_times(w, groups, "v1_cost_sensitive", cs, line=1.0)
    t_thr = migration_times(w, groups, "threshold", matched, line=tau_m)
    lead = {}
    for name, sel, t in (("v1_cost_sensitive", cs, t_cs), ("threshold_matched_v1", matched, t_thr)):
        caught = sel & w.failed
        d = w.cutoff[caught] - t[caught]
        lead[name] = {
            "necessary_migrations": int(caught.sum()),
            "median_lead_days": float(np.median(d)),
            "share_lead_over_30_days": float((d > 30).mean()),
            "share_lead_over_365_days": float((d > 365).mean()),
        }
    by_window = {}
    for win in WINDOWS:
        c1, c2 = total_cost(w, cs, t_cs, win), total_cost(w, matched, t_thr, win)
        by_window["inf" if not np.isfinite(win) else str(int(win))] = delta(c1, c2)
    exact = {}
    thr_k = select_budget(w, "threshold", "count", int(cs.sum()), V1_SEED)
    thr_gb = select_budget(w, "threshold", "gb", float(w.GB[cs].sum()), V1_SEED)
    for name, sel_t in (("exact_count", thr_k), ("same_gb", thr_gb)):
        tt = migration_times(w, groups, "threshold", sel_t)
        exact[name] = {
            ("inf" if not np.isfinite(win) else str(int(win))): delta(
                total_cost(w, cs, t_cs, win), total_cost(w, sel_t, tt, win)
            )
            for win in WINDOWS
        }
    base = exact["exact_count"]["inf"]
    vals = list(exact["exact_count"].values())
    moves = [abs(v - base) for v in vals]
    flips = any(np.sign(v) != np.sign(base) for v in vals)
    verdict = "confirmed" if (max(moves) >= 0.01 or flips) else "rejected"
    return {
        "lead_time": lead,
        "delta_by_accounting_window_days": by_window,
        "delta_by_window_exact_budgets": exact,
        "verdict": verdict,
        "note": "window W: a migration averts the failure only if it happens within W days; "
        "W = 7 mirrors Narya's default unallocatable period",
    }


def h8_within_host_order(w, vm, host_of_vm, budget_gb, seed):
    gb = vm["memory_gb"].to_numpy(float)
    fail_vm = vm["failure_customer_cost_min"].to_numpy(float)
    mig_vm = (vm["migration_resource_cost_min"] + vm["migration_customer_cost_min"]).to_numpy()
    tie = np.random.default_rng(seed).random(len(w.pmax))
    host_order = np.lexsort((tie, -w.pmax))
    cum = np.cumsum(w.GB[host_order])
    j = int(np.searchsorted(cum, budget_gb, side="right"))  # first host that does not fit
    full = host_order[:j]
    boundary = host_order[j]
    left = budget_gb - (cum[j - 1] if j else 0.0)
    vms = np.flatnonzero(host_of_vm == boundary)
    base = float(w.M[full].sum() + w.F[w.failed].sum() - w.F[full][w.failed[full]].sum())
    rng = np.random.default_rng(seed)
    orders = {
        "smallest_first": np.argsort(gb[vms], kind="stable"),
        "largest_first": np.argsort(-gb[vms], kind="stable"),
        "random": rng.permutation(vms.size),
    }
    costs = {}
    for name, o in orders.items():
        moved = vms[o][np.cumsum(gb[vms][o]) <= left]
        extra = mig_vm[moved].sum()
        if w.failed[boundary]:
            extra -= fail_vm[moved].sum()
        costs[name] = base + float(extra)
    spread = (max(costs.values()) - min(costs.values())) / min(costs.values())
    return {
        "costs": costs,
        "relative_spread": spread,
        "boundary_host_vms": int(vms.size),
        "verdict": "rejected" if spread < 0.001 else "inconclusive",
        "note": "v1 moves whole hosts, so only the one host at the budget boundary can be "
        "split; the order of VMs matters nowhere else",
    }


# ---------------------------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------------------------
def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8)


def fig_budgets(rows, path):
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    labels = [r[0] for r in rows]
    vals = [100 * r[1] for r in rows]
    colors = [OKABE_ITO[0] if v >= 0 else OKABE_ITO[3] for v in vals]
    ax.barh(labels, vals, color=colors, height=0.6)
    ax.axvline(0, color="black", lw=0.8)
    ax.axvline(-1, color="grey", lw=0.6, ls="--")
    ax.text(-1.05, -0.62, "materiality (1%)", fontsize=7, color="grey", ha="right")
    for i, v in enumerate(vals):
        ax.text(
            v / 2 if v < -0.6 else v + 0.08,
            i,
            f"{v:+.1f}%",
            va="center",
            ha="center" if v < -0.6 else "left",
            fontsize=8,
            color="white" if v < -0.6 else "black",
        )
    ax.set_xlim(min(vals) - 0.3, max(vals) + 0.7)
    ax.set_ylim(len(vals) - 0.5, -0.85)
    ax.set_xlabel("Delta vs threshold (%, positive = v1 rule better)", fontsize=8)
    ax.set_title("What the v1 -3.1% is made of (v1 world, rho = 0)", fontsize=9)
    style(ax)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_calibration(dec, path):
    fig, ax = plt.subplots(figsize=(3.6, 3.4))
    lo = min(dec["mean_p"].min(), dec["obs_rate"].replace(0, np.nan).min()) * 0.7
    hi = max(dec["mean_p"].max(), dec["obs_rate"].max()) * 1.4
    ax.plot([lo, hi], [lo, hi], color="grey", lw=0.8, ls="--")
    err = 1.96 * np.sqrt(dec["expected"]) / dec["n"]
    ax.errorbar(
        dec["mean_p"], dec["obs_rate"], yerr=err, fmt="o", ms=4, color=OKABE_ITO[0], capsize=2
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Predicted 30-day failure probability (decile mean)", fontsize=8)
    ax.set_ylabel("Observed 30-day failure rate", fontsize=8)
    ax.set_title("H1: calibration over host-months", fontsize=9)
    style(ax)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_noise(runs, path):
    fig, ax = plt.subplots(figsize=(4.2, 3.2))
    for i, (win, label) in enumerate(
        ((float("inf"), "any later failure counts (v1)"), (30.0, "30-day accounting"))
    ):
        m = [100 * np.mean(runs[(s, win)]) for s in SIGMAS]
        lo = [100 * np.min(runs[(s, win)]) for s in SIGMAS]
        hi = [100 * np.max(runs[(s, win)]) for s in SIGMAS]
        ax.plot(SIGMAS, m, marker="o", ms=4, color=OKABE_ITO[i], label=label)
        ax.fill_between(SIGMAS, lo, hi, color=OKABE_ITO[i], alpha=0.2, lw=0)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xlabel("Noise on log-odds of p (sigma)", fontsize=8)
    ax.set_ylabel("Delta v1 rule vs threshold, same count (%)", fontsize=8)
    ax.set_title("H5: calibrated synthetic fates, 10 dev seeds", fontsize=9)
    ax.legend(fontsize=7, frameon=False)
    style(ax)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_windows(exact, path):
    fig, ax = plt.subplots(figsize=(4.4, 3.0))
    keys = list(exact["exact_count"])
    for i, (name, label) in enumerate(
        (("exact_count", "same number of hosts"), ("same_gb", "same GB"))
    ):
        ax.plot(
            range(len(keys)),
            [100 * exact[name][k] for k in keys],
            marker="o",
            ms=4,
            color=OKABE_ITO[i],
            label=label,
        )
    ax.set_xticks(range(len(keys)), [k if k != "inf" else "any time" for k in keys])
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xlabel("A migration averts a failure only within this many days", fontsize=8)
    ax.set_ylabel("Delta v1 rule vs threshold (%)", fontsize=8)
    ax.set_title("H6: accounting window", fontsize=9)
    ax.legend(fontsize=7, frameon=False)
    style(ax)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ---------------------------------------------------------------------------------------------
def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    drv, gid, groups, lut, vm = load_inputs()
    host_of_vm = assign(len(vm), len(drv), V1_SEED)
    w = build_world(drv, gid, groups, vm, host_of_vm)

    repro, cs, matched, tau_m = reproduce_v1(w, lut)
    print(f"v1 reproduced: delta {100 * repro['delta_v1']:+.2f}%")

    grid42 = budget_grid(w, groups, cs, V1_SEED)
    grids = {}
    for s in DEV_SEEDS:
        ws = build_world(drv, gid, groups, vm, assign(len(vm), len(drv), s))
        grids[s] = budget_grid(ws, groups, select_line(ws, "v1_cost_sensitive", 1.0), s)
    grid_seeds = {
        k: {
            "mean": float(np.mean([grids[s][k]["delta"] for s in DEV_SEEDS])),
            "sd": float(np.std([grids[s][k]["delta"] for s in DEV_SEEDS], ddof=1)),
            "min": float(np.min([grids[s][k]["delta"] for s in DEV_SEEDS])),
            "max": float(np.max([grids[s][k]["delta"] for s in DEV_SEEDS])),
        }
        for k in grid42
    }

    d_k = grid42["count|1.0|v1_cost_sensitive|inf"]["delta"]
    d_gb = grid42["gb|1.0|v1_cost_sensitive|inf"]["delta"]
    h3 = {
        "v1_count_match": {
            "cs_hosts": repro["cost_sensitive"]["hosts"],
            "threshold_hosts": repro["threshold_matched_v1"]["hosts"],
            "cs_gb": repro["cost_sensitive"]["gb"],
            "threshold_gb": repro["threshold_matched_v1"]["gb"],
        },
        "delta_v1_bisection": repro["delta_v1"],
        "delta_exact_count": d_k,
        "delta_gb_match": d_gb,
        "verdict": "confirmed"
        if d_gb >= -0.01
        else "rejected"
        if d_gb <= -0.02
        else "inconclusive",
    }
    # Pre-written H7 rule, applied to BAM with the budget's own denominator at 1x:
    pre = [
        grid42["count|1.0|bam_count|inf"]["delta"],
        grid42["gb|1.0|bam_gb|inf"]["delta"],
        grid_seeds["count|1.0|bam_count|inf"]["mean"],
        grid_seeds["gb|1.0|bam_gb|inf"]["mean"],
    ]
    # Redesigned test (after the first run showed 1x is degenerate): at a GB budget, does
    # dividing by GB (the budgeted resource) instead of by M (v1) change the result?
    # Only budgets where both rankings spend the whole budget: at 2x BAM stops at positive
    # benefit, which measures the stopping rule, not the denominator.
    denom = {
        f"{m}|{win}": grid_seeds[f"gb|{m}|bam_gb|{win}"]["mean"]
        - grid_seeds[f"gb|{m}|v1_cost_sensitive|{win}"]["mean"]
        for m in MULTS
        if m <= 1.0
        for win in ("inf", "30")
    }
    big = max(abs(v) for v in denom.values())
    h7 = {
        "pre_written_rule_inputs": pre,
        "pre_written_rule_verdict": "confirmed"
        if min(pre) >= -0.01
        else "rejected"
        if max(pre) <= -0.02
        else "inconclusive",
        "gb_denominator_minus_m_denominator_dev_mean": denom,
        "verdict": "confirmed" if big >= 0.01 else "rejected" if big < 0.005 else "inconclusive",
        "corr_M_GB_hosts": float(np.corrcoef(w.M, w.GB)[0, 1]),
        "note": "redesigned after the first run; the pre-written rule is degenerate at 1x",
    }

    h1, dec = h1_calibration(w, groups)
    h1["by_majority_tier"] = per_tier_calibration(w, groups)
    h2 = h2_urgency(lut, w, repro["cost_sensitive"]["cost"])
    h4 = h4_unknown(drv, gid, groups, vm, host_of_vm, V1_SEED)
    h5, per_sigma = h5_noise(w, groups)
    h6 = h6_windows(w, groups, cs, matched, tau_m)
    h8 = h8_within_host_order(w, vm, host_of_vm, repro["cost_sensitive"]["gb"], V1_SEED)

    result = {
        "schema": "v1_anomaly/1",
        "provenance": "DERIVED",
        "inputs": {
            "hosts": len(drv),
            "failures": int(w.failed.sum()),
            "vms": len(vm),
            "placement_seed": V1_SEED,
            "dev_seeds": DEV_SEEDS,
        },
        "delta_definition": "(C_ref - C_policy) / C_ref; positive means the policy is better",
        "verdict_rules": VERDICT_RULES,
        "reproduction": repro,
        "budget_grid_v1_world": grid42,
        "budget_grid_dev_seeds": grid_seeds,
        "H1": h1,
        "H2": h2,
        "H3": h3,
        "H4": h4,
        "H5": h5,
        "H6": h6,
        "H7": h7,
        "H8": h8,
    }
    OUT_JSON.write_text(json.dumps(result, indent=2, default=float))

    fig_budgets(
        [
            ("v1 as published: 5,522 vs 5,116 hosts", repro["delta_v1"]),
            ("Same number of hosts", d_k),
            ("Same GB of VM memory", d_gb),
            ("Same hosts, 30-day accounting", grid42["count|1.0|v1_cost_sensitive|30"]["delta"]),
            ("Same GB, 30-day accounting", grid42["gb|1.0|v1_cost_sensitive|30"]["delta"]),
        ],
        FIG_DIR / "v1_anomaly_budgets.pdf",
    )
    fig_calibration(dec, FIG_DIR / "v1_anomaly_calibration.pdf")
    fig_noise(per_sigma, FIG_DIR / "v1_anomaly_noise.pdf")
    fig_windows(h6["delta_by_window_exact_budgets"], FIG_DIR / "v1_anomaly_windows.pdf")

    for h in ("H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8"):
        print(h, result[h]["verdict"])
    print("wrote", OUT_JSON.relative_to(ROOT))


if __name__ == "__main__":
    main()
