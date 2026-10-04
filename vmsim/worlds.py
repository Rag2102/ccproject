"""Failure worlds: everything random that must be identical across policies (plan Week 12).

A world fixes, for one (config, seed): the hosts and their drives, drive ages, the daily host
hazard matrix, each host's first failure time, the initial VMs (residents present at time 0,
with their elapsed ages) and their placement. Policies
only read it. Worlds are saved as .npz with a SHA-256 over their arrays and listed in
worlds/manifest.csv; the arrays themselves stay out of Git (plan: DVC).

VM arrivals and departures during the run are drawn from their own streams by the engine
(Week 13), so they are also identical across policies.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from vmsim import failure, placement
from vmsim.config import SimConfig
from vmsim.entities import Hosts, make_hosts, sample_present_residents, split
from vmsim.predictor import Oracle
from vmsim.rng import Streams

ROOT = Path(__file__).resolve().parents[1]
WORLDS = ROOT / "worlds"
ARRAYS = (
    "drives",
    "age0",
    "hazard",
    "disk_hazard",
    "fail_t",
    "vm_rows",
    "vm_host",
    "vm_tier",
    "host_risk0",
    "vm_age0",
    "place_blend",
    "host_class",
)


@dataclass(frozen=True)
class World:
    seed: int
    config: dict
    drives: np.ndarray
    age0: np.ndarray
    hazard: np.ndarray  # hosts x days (warm-up + horizon + 3H)
    disk_hazard: np.ndarray
    fail_t: np.ndarray  # first failure time of each host, in days from the start of warm-up
    vm_rows: np.ndarray  # Azure rows of the initial VMs
    vm_host: np.ndarray
    vm_tier: np.ndarray
    host_risk0: np.ndarray  # oracle p_H at day 0, used by placement
    vm_age0: np.ndarray  # days each initial VM has already run at time 0
    place_blend: np.ndarray  # scalar: v1 blend weight that achieved the target rho (else 0 or 1)
    host_class: np.ndarray  # regime B2: host class by risk rank (else all 0)

    def digest(self) -> str:
        h = hashlib.sha256(json.dumps(self.config, sort_keys=True).encode())
        h.update(str(self.seed).encode())
        for name in ARRAYS:
            a = np.ascontiguousarray(getattr(self, name))
            h.update(name.encode() + str(a.dtype).encode() + str(a.shape).encode() + a.tobytes())
        return h.hexdigest()


def n_days(cfg: SimConfig) -> int:
    return cfg.warmup_days + cfg.horizon_days + 3 * cfg.risk_h_days


def generate(cfg: SimConfig, seed: int) -> World:
    s = Streams(seed)
    nd = n_days(cfg)
    fc = cfg.failure
    hosts: Hosts = make_hosts(
        cfg.n_hosts, fc.drives_per_host, cfg.host_mem_gb, s.gen("failures", 0)
    )
    age0 = failure.initial_ages(hosts.drives, s.gen("failures", 1))
    hz, disk = failure.host_hazard(hosts.drives, age0, nd, fc.non_disk_multiplier, fc.weibull_shape)
    fail_t = failure.sample_failure_times(hz, s.gen("failures", 2))
    risk0 = Oracle(hz, cfg.risk_h_days).score(0).p_h

    pc = cfg.placement
    # residents present at time 0, filling init_fill of memory net of the transients' share
    target_gb = pc.init_fill * split()["resident_mem_share"] * hosts.cap_gb.sum()
    vms, age = sample_present_residents(target_gb, s.gen("arrivals", 0))
    rng = s.gen("placement", 0)
    tier = vms.tier
    blend = 0.0
    host_class = np.zeros(cfg.n_hosts, dtype=np.int8)
    if pc.regime == "random":
        host = placement.random(vms, hosts.cap_gb, rng, pc.capacity)
    elif pc.regime == "rho":
        host, blend, _ = placement.rho_controlled(
            vms, hosts.cap_gb, risk0, pc.rho, rng, pc.capacity
        )
    elif pc.regime == "adversarial":
        host = placement.adversarial(vms, hosts.cap_gb, risk0, rng, pc.capacity)
        blend = 1.0
    elif pc.regime == "class":
        host_class = placement.assign_classes(risk0, pc.class_shares)
        n = len(vms)
        host = placement.place_class(
            vms.mem_gb,
            tier,
            hosts.cap_gb.astype(float),
            np.ones(len(hosts.cap_gb), bool),
            host_class,
            np.asarray(pc.class_given_tier),
            rng,
            rng.uniform(size=n),
            rng.uniform(size=n),
        )
        if (host < 0).any():
            raise RuntimeError("regime B2: initial VMs do not fit")
    else:
        raise ValueError(f"placement regime {pc.regime!r} needs inputs the world cannot build yet")
    return World(
        seed=seed,
        config=cfg.to_dict(),
        drives=hosts.drives,
        age0=age0,
        hazard=hz,
        disk_hazard=disk,
        fail_t=fail_t,
        vm_rows=vms.source_row,
        vm_host=host,
        vm_tier=tier,
        host_risk0=risk0,
        vm_age0=age,
        place_blend=np.array(blend),
        host_class=host_class,
    )


def save(w: World, scenario: str, root: Path = WORLDS) -> Path:
    d = root / scenario
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"seed_{w.seed}.npz"
    np.savez_compressed(
        path, **{k: getattr(w, k) for k in ARRAYS}, config=json.dumps(w.config), seed=w.seed
    )
    digest = w.digest()
    man = root / "manifest.csv"
    rows = []
    if man.exists():
        with man.open() as f:
            rows = [
                r
                for r in csv.DictReader(f)
                if not (r["scenario"] == scenario and int(r["seed"]) == w.seed)
            ]
    rows.append(
        {
            "scenario": scenario,
            "seed": w.seed,
            "sha256": digest,
            "hosts": len(w.fail_t),
            "vms": len(w.vm_host),
        }
    )
    rows.sort(key=lambda r: (r["scenario"], int(r["seed"])))
    with man.open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["scenario", "seed", "sha256", "hosts", "vms"])
        wr.writeheader()
        wr.writerows(rows)
    return path


def load(path: Path) -> World:
    z = np.load(path, allow_pickle=False)
    return World(
        seed=int(z["seed"]), config=json.loads(str(z["config"])), **{k: z[k] for k in ARRAYS}
    )
