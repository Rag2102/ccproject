"""Exploratory variants (vmsim/policies/variants.py): BAMWait reduces to BAM when the window is the
full horizon and moves no more when it is shorter; avoid marks take the riskiest hosts."""

import numpy as np

from vmsim.policies.bam import BAM
from vmsim.policies.base import Observation
from vmsim.policies.variants import AvoidTop, BAMAvoid, BAMWait, top_risk_mark


def obs(seed: int = 0, n_hosts: int = 50, n_vm: int = 400) -> Observation:
    r = np.random.default_rng(seed)
    host = r.integers(0, n_hosts, n_vm)
    return Observation(
        day=40,
        h_days=30,
        p_h=r.uniform(0.0, 0.3, n_hosts),
        e_ttf=r.uniform(1, 300, n_hosts),
        host_up=np.ones(n_hosts, dtype=bool),
        host_free_gb=np.full(n_hosts, 50.0),
        vm=np.arange(n_vm),
        vm_host=host,
        vm_mem_gb=r.uniform(1, 30, n_vm),
        vm_tier=r.integers(0, 3, n_vm),
        vm_age_days=r.uniform(1, 100, n_vm),
        vm_fail_cost=r.uniform(3, 10, n_vm),
        vm_survival=r.uniform(0.2, 1.0, n_vm),
        vm_mig_cost=r.uniform(0.01, 0.6, n_vm),
        vm_mig_s=r.uniform(5, 300, n_vm),
        rng=np.random.default_rng(seed),
    )


def test_wait_with_full_window_is_bam():
    o = obs()
    a = BAM().decide(o, 1e9)
    b = BAMWait(window_days=30).decide(obs(), 1e9)
    assert np.array_equal(a, b)


def test_shorter_window_moves_a_subset():
    full = set(BAM().decide(obs(1), 1e9))
    for d in (14, 7, 1):
        short = set(BAMWait(window_days=d).decide(obs(1), 1e9))
        assert short <= full
    assert len(set(BAMWait(window_days=1).decide(obs(1), 1e9))) < len(full)


def test_avoid_marks_the_riskiest_share():
    o = obs(2)
    m = top_risk_mark(o, 0.1)
    assert m.sum() == 5
    assert o.p_h[m].min() >= o.p_h[~m].max()
    assert np.array_equal(AvoidTop(0.1).avoid(o), m)
    assert len(AvoidTop(0.1).decide(o, 1e9)) == 0
    assert np.array_equal(BAMAvoid(0.1).avoid(o), m)
