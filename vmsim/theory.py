"""Closed forms for THEORY.md (T1-T4): one-shot selection under a Gaussian copula.

Model (THEORY.md section 3). Items i = 1..N with equal weight (the budgeted resource, GB, is the
same for every item; the budget is a share q of the items). Each item has a calibrated failure
probability p over the horizon and a value kappa = c e / w of an interruption averted, per unit
of weight. X = log p and Y = log kappa are bivariate normal: means mu_x and 0, SDs s_x and s_y,
correlation rho. Migrating costs mu per unit of weight, given as lam = mu / E[p kappa].

Policies see a score p_hat. log p_hat = gamma (X + s_n eps) + log k, eps ~ N(0, 1) independent;
k keeps the mean of p_hat over items equal to that of p when s_n = 0 (the simulator's miscal).
  P2   ranks by p_hat and moves exactly q of the items (it uses the budget).
  BAM  ranks by p_hat kappa and moves while p_hat kappa > mu, at most q of the items.
Both rules select {W > t} for a linear score W = a X + b Y + a s_n eps. With Z = X + Y,
  E[e^Z 1{W > t}] = M Phi((m_W + Cov(Z, W) - t) / s_W)      (exponential tilting)
  P(W > t)        = Phi((m_W - t) / s_W)
with M = E[p kappa] = exp(mu_x + Var(Z) / 2). Costs are per item and relative to the expected
interruption cost of doing nothing (C_P0 = M). Delta = (C_P2 - C_pi) / C_P2, the protocol's.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from scipy.stats import norm


@dataclass(frozen=True)
class Model:
    rho: float = 0.0  # corr(log p, log kappa)
    s_y: float = 0.5  # SD of log kappa
    q: float = 0.02  # budget, share of items
    lam: float = 1.0  # migration cost per unit weight / E[p kappa]
    s_n: float = 0.0  # noise SD on log p seen by the policies
    gamma: float = 1.0  # miscalibration exponent
    s_x: float = 1.0  # SD of log p
    mu_x: float = float(np.log(0.01))  # mean of log p (p < 1 for all but ~1e-6 of items)

    def with_(self, **kw) -> Model:
        return replace(self, **kw)

    @property
    def var_z(self) -> float:
        return self.s_x**2 + 2 * self.rho * self.s_x * self.s_y + self.s_y**2

    @property
    def M(self) -> float:
        return float(np.exp(self.mu_x + self.var_z / 2))

    @property
    def mu(self) -> float:
        return self.lam * self.M

    @property
    def log_k(self) -> float:
        g, m, s = self.gamma, self.mu_x, self.s_x
        return (m + s**2 / 2) - (g * m + g**2 * s**2 / 2)


def _score(m: Model, a: float, b: float) -> tuple[float, float, float]:
    """Mean, SD and Cov(Z, W) of W = a X + b Y + a s_n eps."""
    sx, sy, r = m.s_x, m.s_y, m.rho
    mean = a * m.mu_x
    var = a * a * sx * sx + 2 * a * b * r * sx * sy + b * b * sy * sy + (a * m.s_n) ** 2
    cov = a * sx * sx + (a + b) * r * sx * sy + b * sy * sy
    return mean, float(np.sqrt(var)), cov


def _select(m: Model, a: float, b: float, stop: float | None) -> dict:
    mean, sd, cov = _score(m, a, b)
    t = mean - sd * norm.ppf(m.q)  # moves exactly q of the items
    if stop is not None:
        t = max(t, stop)
    share = float(norm.cdf((mean - t) / sd))
    gain = m.M * float(norm.cdf((mean + cov - t) / sd))
    return {"share": share, "gain": gain, "benefit": gain - m.mu * share}


def p2(m: Model) -> dict:
    return _select(m, 1.0, 0.0, None)


def bam(m: Model) -> dict:
    # p_hat kappa > mu  <=>  gamma (X + s_n eps) + Y > log mu - log k
    return _select(m, m.gamma, 1.0, float(np.log(m.mu) - m.log_k) if m.mu > 0 else None)


def delta(m: Model) -> float:
    """Delta of BAM vs P2: (C_P2 - C_BAM) / C_P2, with C = M - benefit."""
    b2, bb = p2(m)["benefit"], bam(m)["benefit"]
    return (bb - b2) / (m.M - b2)


def ranking_gap(m: Model) -> float:
    """T3's ranking term, no noise, budget binding for both rules:
    Phi(z + s_z) - Phi(z + s_x + rho s_y), as a share of C_P0.
    Non-negative; zero iff s_y = 0 or rho = 1."""
    z = norm.ppf(m.q)
    return float(norm.cdf(z + np.sqrt(m.var_z)) - norm.cdf(z + m.s_x + m.rho * m.s_y))


def noise_flip(m: Model) -> float | None:
    """T4: the noise SD above which BAM's ranking term turns negative (budget binding for both,
    gamma = 1), or None if it never does. A flip exists iff A = s_x^2 + rho s_x s_y > Var(Z)."""
    vz = m.var_z
    a = m.s_x**2 + m.rho * m.s_x * m.s_y
    if a <= vz:
        return None
    s2 = (vz * vz * m.s_x**2 - a * a * vz) / (a * a - vz * vz)
    return float(np.sqrt(max(s2, 0.0)))


# --------------------------------------------------------------------------- Monte Carlo
def monte_carlo(m: Model, n: int = 200_000, reps: int = 10, seed: int = 0) -> dict:
    """Draw items from the model, select by both rules, return Delta from expected benefit given
    the draws (p kappa - mu; exact given p) and from realised benefit (Bernoulli failures), pooled
    over reps, with jackknife SEs over reps."""
    rng = np.random.default_rng(seed)
    k = int(round(m.q * n))
    cov = [[m.s_x**2, m.rho * m.s_x * m.s_y], [m.rho * m.s_x * m.s_y, m.s_y**2]]
    rows = []
    for _ in range(reps):
        xy = rng.multivariate_normal([m.mu_x, 0.0], cov, n)
        p = np.minimum(np.exp(xy[:, 0]), 1.0)
        kap = np.exp(xy[:, 1])
        fail = rng.random(n) < p
        xhat = xy[:, 0] + m.s_n * rng.standard_normal(n)
        lp = m.gamma * xhat + m.log_k
        top2 = np.argpartition(-xhat, k - 1)[:k] if k else np.array([], int)
        dens = lp + xy[:, 1]
        topb = np.argpartition(-dens, k - 1)[:k] if k else np.array([], int)
        topb = topb[dens[topb] > np.log(m.mu)] if m.mu > 0 else topb
        exp_all, real_all = float((p * kap).sum()), float((fail * kap).sum())
        r = {}
        for name, sel in (("P2", top2), ("BAM", topb)):
            r[name + "_exp"] = exp_all - float((p[sel] * kap[sel]).sum()) + m.mu * len(sel)
            r[name + "_real"] = real_all - float((fail[sel] * kap[sel]).sum()) + m.mu * len(sel)
        rows.append(r)
    out = {}
    for kind in ("exp", "real"):
        a = np.array([r["P2_" + kind] for r in rows])
        b = np.array([r["BAM_" + kind] for r in rows])
        est = (a.sum() - b.sum()) / a.sum()
        jk = np.array([(a.sum() - a[i] - b.sum() + b[i]) / (a.sum() - a[i]) for i in range(reps)])
        se = float(np.sqrt((reps - 1) / reps * ((jk - jk.mean()) ** 2).sum()))
        out[kind] = {"delta": float(est), "se": se}
    return out
