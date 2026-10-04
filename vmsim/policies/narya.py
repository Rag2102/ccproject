"""P5, Narya-inspired (plan Week 15; reading/levy2020narya.md; docs/v2/narya_differences.md).

Narya decides per flagged node, not per VM. It picks an action by Thompson sampling, keeps it
for that node (sticky), and learns from the interruptions observed over a delayed window. Two
variants:

  simple    the plan's v5 specification. Actions {nothing, migrate, avoid}; context = risk
            bucket; Beta posterior per (bucket, action) on "no interruption on the host during
            the window"; window = H days; the action with the highest sampled success wins.
  faithful  closer to the paper. Actions {NoOp, UA (avoid allocation), UA-LM (avoid, then
            live-migrate)}; Gamma prior on a Poisson rate of cost per episode (interruption +
            migration cost in minutes, the reward is a cost); lowest sampled rate wins;
            exponential decay 0.99 per update; a 10% exploration floor; 14-day window.

Both: a host is flagged when its p_H is in the top `flag_share` of up hosts that day (Narya's
predictor flags few nodes); the bucket is the host's rank among flagged hosts (thirds). An
episode starts when a host is flagged without an active episode, and ends after the window or
when the host's life ends (failure and repair). "migrate" drains the host: its eligible VMs are
offered every day of the episode, riskiest host first. Feedback comes only from
`obs.feedback` (outcomes observed after the fact). After a migration there is no counterfactual:
the policy never learns what the VMs it moved would have suffered (censored feedback).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from vmsim.policies.base import Observation, Policy

ACTIONS = {"simple": ("nothing", "migrate", "avoid"), "faithful": ("noop", "ua", "ua-lm")}
MIGRATES = {"migrate", "ua-lm"}
AVOIDS = {"avoid", "ua", "ua-lm"}


@dataclass
class Episode:
    action: str
    bucket: int
    start: int
    life: int
    cost: float = 0.0
    interrupted: bool = False


@dataclass
class Posterior:
    a: dict = field(default_factory=dict)  # (bucket, action) -> parameter 1
    b: dict = field(default_factory=dict)  # (bucket, action) -> parameter 2


class Narya(Policy):
    def __init__(
        self,
        variant: str = "simple",
        flag_share: float = 0.02,
        n_buckets: int = 3,
        window: int | None = None,
        decay: float = 0.99,
        explore: float = 0.10,
        name: str | None = None,
    ):
        if variant not in ACTIONS:
            raise ValueError(f"unknown variant {variant!r}")
        self.variant, self.flag_share, self.n_buckets = variant, flag_share, n_buckets
        self.window = window if window is not None else (None if variant == "simple" else 14)
        self.decay, self.explore = decay, explore
        self.name = name or ("P5" if variant == "simple" else "P5-faithful")
        self.reset()

    def reset(self) -> None:
        self.episodes: dict[int, Episode] = {}
        self.post = Posterior()
        self.log: list[tuple] = []  # (day, host, bucket, action) per decision
        self.updates = 0

    # ---------------------------------------------------------------- learning
    def _prior(self, key):
        if self.variant == "simple":  # Beta(1, 1) on success
            return self.post.a.get(key, 1.0), self.post.b.get(key, 1.0)
        return self.post.a.get(key, 1.0), self.post.b.get(key, 0.1)  # Gamma(shape, rate)

    def _update(self, ep: Episode) -> None:
        key = (ep.bucket, ep.action)
        a, b = self._prior(key)
        if self.variant == "simple":
            ok = 0.0 if ep.interrupted else 1.0
            self.post.a[key], self.post.b[key] = a + ok, b + (1 - ok)
        else:  # Poisson count of cost minutes per episode, with exponential decay
            a0, b0 = 1.0, 0.1
            a = a0 + self.decay * (a - a0) + round(ep.cost)
            b = b0 + self.decay * (b - b0) + 1.0
            self.post.a[key], self.post.b[key] = a, b
        self.updates += 1

    def _choose(self, bucket: int, rng: np.random.Generator) -> str:
        acts = ACTIONS[self.variant]
        if self.variant == "faithful" and rng.uniform() < self.explore:
            return acts[int(rng.integers(len(acts)))]
        draws = []
        for act in acts:
            a, b = self._prior((bucket, act))
            if self.variant == "simple":
                draws.append(rng.beta(a, b))  # success probability: higher is better
            else:
                draws.append(-rng.gamma(a, 1.0 / b))  # cost rate: lower is better
        return acts[int(np.argmax(draws))]

    # ---------------------------------------------------------------- daily step
    def _step(self, obs: Observation) -> None:
        fb, window = obs.feedback, self.window or obs.h_days
        life = obs.host_life_start
        for h, ep in list(self.episodes.items()):
            if fb is not None:
                ep.cost += fb.interrupt_cost[h] + fb.migration_cost[h]
                ep.interrupted |= fb.interrupt_cost[h] > 0
            ended = obs.day - ep.start >= window or (life is not None and life[h] != ep.life)
            if ended:
                self._update(ep)
                del self.episodes[h]
        up = obs.host_up | (obs.host_avoid if obs.host_avoid is not None else False)
        ups = np.flatnonzero(up)
        if len(ups) == 0:
            return
        k = max(1, int(round(self.flag_share * len(ups))))
        flagged = ups[np.argsort(-obs.p_h[ups], kind="stable")[:k]]
        for rank, h in enumerate(flagged):
            h = int(h)
            if h in self.episodes:
                continue
            bucket = min(self.n_buckets - 1, rank * self.n_buckets // k)
            act = self._choose(bucket, obs.rng)
            self.episodes[h] = Episode(
                act, bucket, obs.day, int(life[h]) if life is not None else -1
            )
            self.log.append((obs.day, h, bucket, act))

    def decide(self, obs: Observation, budget_gb: float) -> np.ndarray:
        self._step(obs)
        drain = [h for h, ep in self.episodes.items() if ep.action in MIGRATES]
        if not drain:
            return np.zeros(0, dtype=np.int64)
        m = np.isin(obs.vm_host, drain)
        if not m.any():
            return np.zeros(0, dtype=np.int64)
        tie = obs.rng.uniform(size=int(m.sum()))
        idx = np.lexsort((tie, obs.vm_host[m], -obs.p_h[obs.vm_host[m]]))
        return obs.vm[m][idx]

    def avoid(self, obs: Observation) -> np.ndarray:
        mark = np.zeros(len(obs.p_h), dtype=bool)
        for h, ep in self.episodes.items():
            if ep.action in AVOIDS:
                mark[h] = True
        return mark

    def action_counts(self) -> dict:
        out: dict = {}
        for _, _, b, a in self.log:
            out.setdefault(f"bucket{b}", {}).setdefault(a, 0)
            out[f"bucket{b}"][a] += 1
        return out
