import numpy as np
import pytest

from vmsim import failure, worlds
from vmsim.config import SimConfig
from vmsim.predictor import Miscalibrated, Noisy, Oracle
from vmsim.rng import Streams


def small_cfg(**kw):
    return SimConfig(n_hosts=1_000, horizon_days=180, **kw)


@pytest.fixture(scope="module")
def world():
    return worlds.generate(small_cfg(), seed=1)


def test_constant_hazard_gives_exponential_times():
    h = np.full((20_000, 3_000), 0.01)
    t = failure.sample_failure_times(h, np.random.default_rng(0))
    lam = -np.log(1 - 0.01)
    assert abs(t.mean() - 1 / lam) < 3 * (1 / lam) / np.sqrt(len(t))
    assert np.isfinite(t).all()


def test_weibull_scale_matches_target():
    for p, k in ((0.02, 0.7), (0.1, 0.5)):
        scale = failure.weibull_scale_for(p, k)
        h = failure.weibull_daily(np.zeros(1), 365, k, scale)
        assert abs((1 - np.prod(1 - h)) - p) < 1e-9


def test_self_calibration_30_days(world):
    """Simulated 30-day failures over 1,000 hosts match the predicted probabilities (plan W12)."""
    p = Oracle(world.hazard, 30).score(0).p_h
    failed = world.fail_t < 30
    z = (failed.sum() - p.sum()) / np.sqrt((p * (1 - p)).sum())
    assert abs(z) < 3, z
    # and over many independent worlds of the same hosts, per decile of p
    sims = np.stack(
        [
            failure.sample_failure_times(world.hazard[:, :30], np.random.default_rng(s)) < 30
            for s in range(200)
        ]
    )
    dec = np.digitize(p, np.quantile(p, np.linspace(0.1, 0.9, 9)))
    for d in range(10):
        m = dec == d
        obs, exp = sims[:, m].sum(), 200 * p[m].sum()
        assert abs(obs - exp) < 4 * np.sqrt(200 * (p[m] * (1 - p[m])).sum()) + 1


def test_same_seed_same_world_and_crn_across_placement():
    a = worlds.generate(small_cfg(), seed=3)
    b = worlds.generate(small_cfg(), seed=3)
    assert a.digest() == b.digest()
    c = worlds.generate(
        small_cfg().with_(placement=small_cfg().placement.__class__(regime="adversarial")), seed=3
    )
    assert np.array_equal(a.fail_t, c.fail_t)  # failures do not depend on placement (CRN)
    assert worlds.generate(small_cfg(), seed=4).digest() != a.digest()


def test_save_load_round_trip(tmp_path, world):
    path = worlds.save(world, "unit", root=tmp_path)
    assert worlds.load(path).digest() == world.digest()
    assert (tmp_path / "manifest.csv").read_text().count("unit") == 1


def test_oracle_matches_direct_product(world):
    o = Oracle(world.hazard, 30)
    for day in (0, 17, 100):
        direct = 1 - np.prod(1 - world.hazard[:, day : day + 30], axis=1)
        assert np.allclose(o.score(day).p_h, direct, rtol=1e-9, atol=1e-15)


def test_e_ttf_constant_hazard():
    h = np.full((3, 400), 0.01)
    e = Oracle(h).score(0).e_ttf
    assert np.allclose(e, 1 / 0.01, rtol=0.02)


def test_noise_and_miscalibration_identities(world):
    o = Oracle(world.hazard, 30)
    assert np.array_equal(Noisy(o, 0.0, Streams(1)).score(5).p_h, o.score(5).p_h)
    assert np.array_equal(Miscalibrated(o, 1.0).score(5).p_h, o.score(5).p_h)
    m = Miscalibrated(o, 0.5).score(5)
    assert abs(m.p_h.mean() - o.score(5).p_h.mean()) < 1e-12  # mean preserved
    n1, n2 = Noisy(o, 1.0, Streams(1)).score(5), Noisy(o, 1.0, Streams(1)).score(5)
    assert np.array_equal(n1.p_h, n2.p_h)  # noise is part of the world (CRN)
