"""In-repo Morris screening (Week 20): ranks a known function's factors correctly."""

import numpy as np

from vmsim import morris


def test_trajectories_move_one_factor_per_step_within_bounds():
    t = morris.trajectories(k=5, r=12, p=4, seed=1)
    assert t.shape == (12, 6, 5) and t.min() >= 0 and t.max() <= 1
    steps = np.abs(np.diff(t, axis=1))
    assert ((steps > 1e-12).sum(axis=2) == 1).all()  # exactly one factor moves per step
    assert np.allclose(steps.max(axis=2), 4 / 6)


def test_ranks_a_known_function():
    """f = 10 x0 + 3 x1 + x2 x3 (interaction) + 0 x4: mu* ranks x0 > x1 > {x2, x3} > x4; the
    interacting factors have sigma > 0, the linear ones sigma ~ 0."""
    names = ["x0", "x1", "x2", "x3", "x4"]
    t = morris.trajectories(k=5, r=40, p=4, seed=2)
    y = 10 * t[..., 0] + 3 * t[..., 1] + 4 * t[..., 2] * t[..., 3]
    rows = {r["factor"]: r for r in morris.summarise(morris.effects(t, y), names)}
    assert rows["x0"]["rank"] == 1 and rows["x1"]["rank"] == 2 and rows["x4"]["rank"] == 5
    assert abs(rows["x0"]["mu_star"] - 10) < 1e-9 and rows["x0"]["sigma"] < 1e-9
    assert rows["x2"]["sigma"] > 0.1 and rows["x4"]["mu_star"] == 0


def test_scale_log_and_linear():
    u = np.array([0.0, 0.5, 1.0])
    assert np.allclose(morris.scale(u, 2, 4), [2, 3, 4])
    assert np.allclose(morris.scale(u, 1, 100, log=True), [1, 10, 100])
