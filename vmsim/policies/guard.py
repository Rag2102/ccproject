"""P6, the safe-adaptive guard (plan Week 16; PROTOCOL section 2).

P6 runs P2 unless the evidence says BAM is better *and* the predictor is calibrated:

  plug-in advantage  Each day, the model's expected benefit of BAM's plan minus P2's, per host:
                     sum of b_i = p_j c_i - m_i (e = 1) over the VMs each plan would move within
                     the GB budget (the engine's first-fit rule, without destinations). Divided by
                     the model's expected interruption cost of doing nothing (sum p_j c_i).
                     Model-based: it needs no counterfactual outcomes.
  sequential looks   Every `look_every` days after the first H days. The lower bound of Delta-hat
                     is a one-sided host-level bootstrap quantile at alpha_k = alpha 6 / (pi^2
                     k^2) for look k (sum over k = alpha), so repeated looks are valid.
  calibration audit  Snapshots of p_H are taken every `look_every` days. A snapshot matures H days
                     later: did the host fail within the H days? Over the snapshots that matured
                     in the last `audit_window` days (rolling, so drift is not diluted by old
                     evidence), the reliability slope (logistic regression of the outcome on
                     logit p) must lie in `slope_band`, with at least `min_events` failures;
                     otherwise P2 is forced.
  switch rule        BAM after two consecutive looks with lower bound > 0 and the audit passing
                     (hysteresis); back to P2 at the first look that fails either. Every switch is
                     logged with its evidence (`self.switches`).

The audit uses only outcomes an operator observes (the engine's daily Feedback), and P6 never
sees the truth. With a well-calibrated predictor the plug-in advantage of BAM is usually
positive, so the audit is the guard's real protection: on the pure-noise control the slope is
near 0 and P6 must stay on P2.
"""

from __future__ import annotations

import numpy as np

from vmsim.policies.bam import BAM
from vmsim.policies.base import Observation, Policy
from vmsim.policies.reference import Threshold


def _kept(plan_idx: np.ndarray, gb: np.ndarray, budget: float) -> np.ndarray:
    """Positions within plan_idx that the engine's first-fit budget rule would keep."""
    keep, left = [], budget
    for k, i in enumerate(plan_idx):
        if gb[i] <= left + 1e-9:
            keep.append(k)
            left -= gb[i]
    return np.asarray(keep, dtype=np.int64)


def reliability_slope(p: np.ndarray, y: np.ndarray) -> float:
    """Slope of a logistic regression of y on logit(p) (1 = calibrated ranking and spread)."""
    from sklearn.linear_model import LogisticRegression

    x = np.log(np.clip(p, 1e-9, 1 - 1e-9) / np.clip(1 - p, 1e-9, 1))[:, None]
    if y.min() == y.max():
        return np.nan
    return float(LogisticRegression(C=1e6, max_iter=1000).fit(x, y).coef_[0, 0])


class SafeGuard(Policy):
    name = "P6"

    def __init__(
        self,
        p2: Threshold,
        bam: BAM | None = None,
        look_every: int = 7,
        alpha: float = 0.05,
        n_boot: int = 500,
        slope_band: tuple[float, float] = (0.8, 1.25),
        min_events: int = 30,
        audit_window: int = 90,
        passes_needed: int = 2,
        name: str = "P6",
    ):
        self.p2, self.bam = p2, bam or BAM()
        self.look_every, self.alpha, self.n_boot = look_every, alpha, n_boot
        self.slope_band, self.min_events, self.passes_needed = slope_band, min_events, passes_needed
        self.audit_window = audit_window
        self.name = name
        self.reset()

    def reset(self) -> None:
        self.p2.reset()
        self.bam.reset()
        self.mode = "P2"
        self.d_host = None  # accumulated per-host (BAM - P2) expected benefit
        self.e_host = None  # accumulated per-host expected cost of doing nothing
        self.snaps: list[tuple[int, np.ndarray, np.ndarray]] = []  # (day, hosts, p)
        self.fail_days: dict[int, list[int]] = {}
        self.looks = 0
        self.passes = 0
        self.switches: list[dict] = []
        self.look_log: list[dict] = []
        self.mode_days = {"P2": 0, "BAM": 0}

    # ---------------------------------------------------------------- evidence
    def _accumulate(self, obs: Observation, plans: dict, budget: float) -> None:
        n = len(obs.p_h)
        if self.d_host is None:
            self.d_host, self.e_host = np.zeros(n), np.zeros(n)
        p, c, m, _ = self.bam.terms(obs)
        b = p * c - m
        pos = {v: k for k, v in enumerate(obs.vm)}
        sums = {}
        for name, plan in plans.items():
            idx = np.array([pos[v] for v in plan], dtype=np.int64)
            kept = idx[_kept(idx, obs.vm_mem_gb, budget)] if len(idx) else idx
            sums[name] = np.bincount(obs.vm_host[kept], weights=b[kept], minlength=n)
        self.d_host += sums["BAM"] - sums["P2"]
        self.e_host += np.bincount(obs.vm_host, weights=p * c, minlength=n)

    def _audit(self, day: int, h_days: int) -> tuple[bool, float, int]:
        ps, ys = [], []
        for d0, hosts, p in self.snaps:
            # matured, and within the rolling window (so calibration drift is not diluted)
            if d0 + h_days > day or d0 + h_days < day - self.audit_window:
                continue
            y = np.array(
                [any(d0 < f <= d0 + h_days for f in self.fail_days.get(int(h), [])) for h in hosts]
            )
            ps.append(p)
            ys.append(y)
        if not ps:
            return False, np.nan, 0
        p, y = np.concatenate(ps), np.concatenate(ys).astype(int)
        events = int(y.sum())
        if events < self.min_events:
            return False, np.nan, events
        slope = reliability_slope(p, y)
        ok = bool(np.isfinite(slope) and self.slope_band[0] <= slope <= self.slope_band[1])
        return ok, slope, events

    def _look(self, obs: Observation) -> None:
        self.looks += 1
        k = self.looks
        alpha_k = self.alpha * 6 / (np.pi**2 * k**2)
        d, e = self.d_host, self.e_host
        est = float(d.sum() / max(e.sum(), 1e-12))
        rng = np.random.default_rng((obs.day, 6))
        hosts = np.flatnonzero(e > 0)
        reps = np.empty(self.n_boot)
        for r in range(self.n_boot):
            s = hosts[rng.integers(0, len(hosts), len(hosts))]
            reps[r] = d[s].sum() / max(e[s].sum(), 1e-12)
        lower = float(np.quantile(reps, alpha_k))
        audit_ok, slope, events = self._audit(obs.day, obs.h_days)
        passed = lower > 0 and audit_ok
        self.passes = self.passes + 1 if passed else 0
        new = self.mode
        if self.mode == "P2" and self.passes >= self.passes_needed:
            new = "BAM"
        elif self.mode == "BAM" and not passed:
            new = "P2"
        rec = {
            "day": obs.day,
            "look": k,
            "alpha_k": alpha_k,
            "delta_hat": est,
            "lower": lower,
            "slope": slope,
            "events": events,
            "audit_ok": audit_ok,
            "mode": new,
        }
        self.look_log.append(rec)
        if new != self.mode:
            self.switches.append({**rec, "from": self.mode, "to": new})
            self.mode = new

    # ---------------------------------------------------------------- policy
    def decide(self, obs: Observation, budget_gb: float) -> np.ndarray:
        if obs.feedback is not None:
            for h in obs.feedback.failed:
                self.fail_days.setdefault(int(h), []).append(obs.day - 1)
        plans = {"P2": self.p2.decide(obs, budget_gb), "BAM": self.bam.decide(obs, budget_gb)}
        self._accumulate(obs, plans, budget_gb)
        if obs.day % self.look_every == 0:
            up = np.flatnonzero(obs.host_up)
            self.snaps.append((obs.day, up, obs.p_h[up].copy()))
            if obs.day >= obs.h_days:
                self._look(obs)
        self.mode_days[self.mode] += 1
        return plans[self.mode]
