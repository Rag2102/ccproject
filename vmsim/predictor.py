"""Predictor interface (plan Week 12; SIM_SPEC section 9).

score(world, day) -> Scores(p_h, e_ttf, p_interval), one value per host:
  p_h         P(host fails in (day, day + H] | up at day)
  e_ttf       expected days to failure (the tail beyond the hazard matrix uses its last hazard)
  p_interval  P(fail in each of the next three H-day intervals | up at day)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Scores:
    p_h: np.ndarray
    e_ttf: np.ndarray
    p_interval: np.ndarray


class Oracle:
    """The true conditional probabilities of the world's hazard matrix."""

    def __init__(self, hazard: np.ndarray, h_days: int = 30):
        self.h = h_days
        self.hazard = hazard
        logs = np.log1p(-np.clip(hazard, 0, 1 - 1e-15))
        self.cum = np.concatenate([np.zeros((len(hazard), 1)), np.cumsum(logs, axis=1)], axis=1)
        surv = np.exp(self.cum[:, 1:])  # P(up after day k | up at 0)
        self.rev_surv = np.cumsum(surv[:, ::-1], axis=1)[:, ::-1]  # sum_{j>=k} surv_j
        last = np.clip(hazard[:, -1], 1e-12, 1)
        self.tail = surv[:, -1] * (1 - last) / last  # geometric tail beyond the matrix

    def _p(self, day: int, a: int, b: int) -> np.ndarray:
        n = self.cum.shape[1] - 1
        lo, hi = min(day + a, n), min(day + b, n)
        return np.exp(self.cum[:, lo] - self.cum[:, day]) - np.exp(
            self.cum[:, hi] - self.cum[:, day]
        )

    def score(self, day: int) -> Scores:
        h = self.h
        p_int = np.stack([self._p(day, k * h, (k + 1) * h) for k in range(3)], axis=1)
        n = self.hazard.shape[1]
        rest = (self.rev_surv[:, day] if day < n else 0.0) + self.tail
        # mid-day convention: a failure within day d counts as half a day
        e_ttf = 0.5 + rest / np.exp(self.cum[:, day])
        return Scores(p_h=p_int[:, 0], e_ttf=e_ttf, p_interval=p_int)


def _logit(p):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return np.log(p / (1 - p))


def _expit(x):
    return 1 / (1 + np.exp(-x))


class Noisy:
    """Oracle with Gaussian noise of s.d. sigma on the logit, one draw per host and day."""

    def __init__(self, oracle: Oracle, sigma: float, streams, h_days: int = 30):
        self.o, self.sigma, self.streams = oracle, sigma, streams

    def score(self, day: int) -> Scores:
        s = self.o.score(day)
        if self.sigma == 0:
            return s
        z = self.streams.gen("predictor", day).normal(size=len(s.p_h))
        shift = self.sigma * z
        p_int = _expit(_logit(s.p_interval) + shift[:, None])
        return Scores(p_h=p_int[:, 0], e_ttf=s.e_ttf, p_interval=p_int)


class Miscalibrated:
    """p' = p**gamma, renormalised so the mean over hosts is unchanged (plan Week 12).

    gamma < 1 compresses the spread of p (under-confident ranking of risk), gamma > 1 widens it.
    """

    def __init__(self, oracle: Oracle, gamma: float):
        self.o, self.gamma = oracle, gamma

    def score(self, day: int) -> Scores:
        s = self.o.score(day)
        if self.gamma == 1:
            return s
        q = s.p_interval**self.gamma
        q = np.clip(
            q * (s.p_interval.mean(axis=0) / np.maximum(q.mean(axis=0), 1e-300)), 0, 1 - 1e-12
        )
        return Scores(p_h=q[:, 0], e_ttf=s.e_ttf, p_interval=q)


class TrainedModel:
    """The calibrated Week 7 model on replayed drive histories: plugged in after Week 7."""

    def __init__(self, *_, **__):
        raise NotImplementedError("needs the Week 7 model (data/v2/models/v2_h30.joblib)")
