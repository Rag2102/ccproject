"""Run configuration as frozen dataclasses, loaded from YAML (SIM_SPEC section 11).

Unknown keys are an error, so a typo in a scenario card cannot silently fall back to a default.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class MigrationConfig:
    nic_gbps: float = 10.0
    usable_share: float = 0.5
    max_concurrent: int = 2
    max_rounds: int = 30
    stop_copy_mb: float = 50.0
    dirty_mbps_at_100pct_cpu: float = 150.0  # v1
    blackout_converged_s: float = 1.0  # v1
    blackout_fallback_s: float = 60.0  # v1
    v1_closed_form: bool = False  # True for the v1 regression (SIM_SPEC section 6)


@dataclass(frozen=True)
class CostConfig:
    d_fail_min: float = 10.0  # v1 UNMITIGATED_FAILURE_DOWNTIME_MIN
    tier_weights: tuple[float, float, float] = (0.3, 0.6, 1.0)  # low, medium, high (v1)
    lambda_bw: float = 1.0  # weight of migration resource minutes (v1 adds both)
    # regime E: SD of log(c / w) over resident VMs (e = s = 1). None keeps v1's costs (natural
    # spread about 1.06: tier 0.51, VM size the rest). Set: interruption costs are rescaled per VM,
    # keeping the median and the order of c / w (engine.kappa_rescale)
    kappa_sigma: float | None = None


@dataclass(frozen=True)
class FailureConfig:
    drives_per_host: int = 4
    hazard_source: str = "v1_lookup"  # "v1_lookup" until the Week 7 model is plugged in
    non_disk_multiplier: float = 1.0  # 0x, 1x, 3x of the disk failure probability per year
    weibull_shape: float = 0.7
    repair_median_days: float = 2.0
    repair_sigma: float = 0.5


@dataclass(frozen=True)
class PlacementConfig:
    regime: str = "random"  # random | rho | class | adversarial
    rho: float = 0.0  # target tie-corrected Spearman for regime "rho"
    # blend weight for arrivals during the run (None: the world's initial blend). Calibrated per
    # regime so the VMs present, not only the initial ones, hit the target (scenarios.py)
    arrival_blend: float | None = None
    # regime D: from switch_day on, arrivals use arrival_blend_after (None: no switch)
    arrival_blend_after: float | None = None
    switch_day: int | None = None
    # regime B2 ("class"): host classes by risk rank with these machine shares (lowest risk
    # first), and P(class | tier) as rows per tier (3 x n_classes); built by scenarios.regime
    class_shares: tuple[float, ...] | None = None
    class_given_tier: tuple[tuple[float, ...], ...] | None = None
    init_fill: float = 0.70
    capacity: str = "gb"  # "gb" (memory) or "slots" (v1: equal VM count per host)


@dataclass(frozen=True)
class SimConfig:
    name: str = "default"
    n_hosts: int = 2_000
    host_mem_gb: float = 144.0  # about 16 VMs per host (v1) x 6.07 GB mean (Azure) / 0.70 fill
    horizon_days: int = 365
    warmup_days: int = 30
    risk_h_days: int = 30
    budget_frac: float = 0.01  # GB per day as a share of cluster memory
    migration: MigrationConfig = field(default_factory=MigrationConfig)
    cost: CostConfig = field(default_factory=CostConfig)
    failure: FailureConfig = field(default_factory=FailureConfig)
    placement: PlacementConfig = field(default_factory=PlacementConfig)

    def with_(self, **kw: Any) -> SimConfig:
        return replace(self, **kw)

    def to_dict(self) -> dict:
        return asdict(self)


_NESTED = {
    "migration": MigrationConfig,
    "cost": CostConfig,
    "failure": FailureConfig,
    "placement": PlacementConfig,
}


def _build(cls, data: dict, where: str):
    known = {f.name: f for f in fields(cls)}
    unknown = set(data) - set(known)
    if unknown:
        raise ValueError(f"{where}: unknown keys {sorted(unknown)}")
    kw = {}
    for k, v in data.items():
        if cls is SimConfig and k in _NESTED:
            kw[k] = _build(_NESTED[k], v or {}, f"{where}.{k}")
        elif isinstance(v, list):
            kw[k] = tuple(v)
        else:
            kw[k] = v
    return cls(**kw)


def from_dict(data: dict) -> SimConfig:
    return _build(SimConfig, data, "config")


def load(path: str | Path) -> SimConfig:
    return from_dict(yaml.safe_load(Path(path).read_text()) or {})
