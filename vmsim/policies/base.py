"""Policy interface (plan Week 14; SIM_SPEC section 10).

Each day the engine builds an Observation and calls `policy.decide(obs, budget_gb)`, which
returns the VMs to migrate in priority order. The engine, not the policy, enforces the budget
(it takes VMs in that order, skipping any whose GB no longer fit and filling the remainder in
order: the protocol's exact-budget rule, within one VM), picks each destination (power of two
choices; the policy may rank the two candidates, by default on p_H) and times the migrations.
So every policy gets the same budget rule and the same destinations rule.

A policy sees only the Observation: scores, host state, the eligible VMs' attributes and
yesterday's outcomes (Feedback: which hosts failed and what was charged, as an operator would
see them). It never sees future failure times or VM departure times, except the oracle (P7),
which declares `oracle = True` and gets `obs.truth`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Truth:
    host_next_fail: np.ndarray  # failure time (days) of each host's current life
    vm_t_depart: np.ndarray  # departure time of each eligible VM (same order as obs.vm)


@dataclass(frozen=True)
class Feedback:
    """What happened during the previous day: outcomes an operator observes after the fact."""

    failed: np.ndarray  # hosts that failed
    interrupt_cost: np.ndarray  # per host: interruption cost charged on it (resident + transient)
    migration_cost: np.ndarray  # per host: migration cost charged with it as the source
    migrated_gb: np.ndarray  # per host: GB that started migrating off it


@dataclass(frozen=True)
class Observation:
    day: int
    h_days: int
    p_h: np.ndarray  # per host
    e_ttf: np.ndarray  # per host, days
    host_up: np.ndarray  # per host: can take VMs (up, not avoided)
    host_free_gb: np.ndarray
    vm: np.ndarray  # eligible VM ids: running, not migrating, age >= MIN_MIGRATE_AGE_DAYS
    vm_host: np.ndarray
    vm_mem_gb: np.ndarray
    vm_tier: np.ndarray
    vm_age_days: np.ndarray
    vm_fail_cost: np.ndarray  # c_i = w_tier x D_fail (minutes), unweighted by survival
    vm_survival: np.ndarray  # s_i: P(still running at a failure H/2 days ahead | age)
    vm_mig_cost: np.ndarray  # m_i estimate: one migration alone on the host's link
    vm_mig_s: np.ndarray  # duration estimate, seconds
    rng: np.random.Generator
    truth: Truth | None = None
    feedback: Feedback | None = None
    host_avoid: np.ndarray | None = None  # per host: currently marked avoid-allocation
    host_life_start: np.ndarray | None = None  # day the host's current life began (-1: first)


class Policy:
    name = "base"
    oracle = False

    def decide(self, obs: Observation, budget_gb: float) -> np.ndarray:
        raise NotImplementedError

    def avoid(self, obs: Observation) -> np.ndarray | None:
        """Hosts to mark avoid-allocation from today (bool per host), or None for no change.
        Called after decide(). A marked host takes no new VMs and is never a destination; a
        repair clears the mark. Only P5 uses it."""
        return None

    def dest_key(self, obs: Observation) -> np.ndarray:
        """Per-host key for choosing between the two random destination candidates (lower is
        better). Every policy uses p_H except the oracle."""
        return obs.p_h

    def __repr__(self) -> str:
        return self.name


def within_host_key(obs: Observation, order: str) -> np.ndarray:
    """Sort key for VMs within a host: smaller key first."""
    if order == "smallest":
        return obs.vm_mem_gb
    if order == "largest":
        return -obs.vm_mem_gb
    if order == "random":
        return obs.rng.uniform(size=len(obs.vm))
    raise ValueError(f"unknown within-host order {order!r}")


def top_hosts_mask(obs: Observation, host_key: np.ndarray, ok: np.ndarray, budget_gb: float):
    """VMs on the hosts that come first by host_key (ascending) among ok hosts, enough to cover
    the budget several times over. A speed-up only: the engine takes VMs in order and stops at
    the budget, so VMs on later hosts could never be reached (the margin covers VMs skipped for
    lack of a destination)."""
    n = len(obs.p_h)
    gb = np.bincount(obs.vm_host, weights=obs.vm_mem_gb, minlength=n)
    hosts = np.flatnonzero(ok & (gb > 0))
    hosts = hosts[np.argsort(host_key[hosts], kind="stable")]
    cum = np.cumsum(gb[hosts])
    k = int(np.searchsorted(cum, 3 * budget_gb + 200.0)) + 1
    keep = np.zeros(n, dtype=bool)
    keep[hosts[:k]] = True
    return keep[obs.vm_host]
