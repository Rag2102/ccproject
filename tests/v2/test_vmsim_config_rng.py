import numpy as np
import pytest

from vmsim import config
from vmsim.rng import STREAMS, Streams


def test_yaml_round_trip(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(
        "n_hosts: 300\nplacement: {regime: rho, rho: 0.3}\ncost: {tier_weights: [0.2, 0.5, 1.0]}\n"
    )
    c = config.load(p)
    assert c.n_hosts == 300 and c.placement.rho == 0.3 and c.cost.tier_weights == (0.2, 0.5, 1.0)
    assert c.migration.nic_gbps == 10.0  # untouched default


def test_unknown_key_is_an_error():
    with pytest.raises(ValueError, match="unknown keys"):
        config.from_dict({"placement": {"rhoo": 0.3}})


def test_streams_deterministic_and_keyed():
    a, b = Streams(7), Streams(7)
    assert np.array_equal(a.gen("failures", 3).random(5), b.gen("failures", 3).random(5))
    # a keyed generator does not depend on what was drawn from other streams before
    b.gen("policy").random(1000)
    assert np.array_equal(a.gen("failures", 3).random(5), b.gen("failures", 3).random(5))
    assert not np.array_equal(a.gen("failures", 3).random(5), a.gen("failures", 4).random(5))
    assert not np.array_equal(
        Streams(7).gen("failures").random(5), Streams(8).gen("failures").random(5)
    )
    assert STREAMS[0] == "failures"  # order is part of the CRN contract
