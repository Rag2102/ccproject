"""ADR-009 cost range: the derivation rule and the "<regime>@<setting>" scenarios."""

import importlib.util
from pathlib import Path

import pytest
import yaml

from vmsim import scenarios
from vmsim.config import SimConfig

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("cr", ROOT / "scripts/v2/38_cost_range.py")
CR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CR)


def src(key, share, dirty, blk, status="extracted"):
    return {
        "key": key,
        "status": status,
        "summary": {"usable_share": share, "dirty_mbps": dirty, "blackout_s": blk},
    }


def test_rule_takes_the_joint_extremes():
    s = [
        src("a", [0.1, 0.5], [2.3], [0.06, 0.21]),
        src("b", [0.3], [40.0], [0.5]),
        src("c", [0.8], [10.0], [0.02]),
        src("d", [0.2], [5.0], [3.0]),
        src("e", [0.9], [999.0], [0.01], status="pending"),
    ]
    out, missing = CR.derive(s)
    assert missing == ["e"]
    lo, hi = out["G0-low"], out["G0-high"]
    assert (lo["usable_share"], lo["dirty_mbps_at_100pct_cpu"], lo["blackout_converged_s"]) == (
        0.8,
        2.3,
        0.02,
    )
    assert (hi["usable_share"], hi["dirty_mbps_at_100pct_cpu"], hi["blackout_converged_s"]) == (
        0.1,
        40.0,
        3.0,
    )
    assert lo["usable_share_from"] == "c" and hi["blackout_converged_s_from"] == "d"


def test_too_few_sources_give_no_settings():
    out, missing = CR.derive([src("a", [0.1], [1.0], [0.1])] * 3)
    assert out is None


def test_split_and_latent_ignore_the_cost_suffix():
    assert scenarios.split_cost("B1@G0-low") == ("B1", "G0-low")
    assert scenarios.split_cost("B1-high") == ("B1-high", None)
    assert scenarios.latent_of("B1@G0-high") == scenarios.latent_of("B1")


def test_setting_overrides_only_the_migration_fields(tmp_path, monkeypatch):
    f = tmp_path / "cost_range.yaml"
    f.write_text(
        yaml.safe_dump(
            {
                "settings": {
                    "G0-low": {
                        "usable_share": 0.8,
                        "dirty_mbps_at_100pct_cpu": 2.3,
                        "blackout_converged_s": 0.06,
                    }
                }
            }
        )
    )
    monkeypatch.setattr(scenarios, "COST_RANGE", f)
    base = SimConfig(n_hosts=50, horizon_days=30, warmup_days=5, name="t")
    a, b = scenarios.regime(base, "C"), scenarios.regime(base, "C@G0-low")
    assert b.migration.usable_share == 0.8 and b.migration.dirty_mbps_at_100pct_cpu == 2.3
    assert b.migration.blackout_converged_s == 0.06
    assert b.placement == a.placement and b.cost == a.cost and b.failure == a.failure
    assert b.name.endswith("@G0-low")
    with pytest.raises(ValueError, match="not derived"):
        scenarios.regime(base, "C@G0-high")
