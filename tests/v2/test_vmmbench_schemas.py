"""vmmbench schemas (plan Week 10, task 4): example files validate, and broken ones do not."""

import copy
import json
from pathlib import Path

import pytest
import yaml

from vmmbench.validate import ValidationError, check, validate

EX = Path(__file__).resolve().parents[2] / "vmmbench" / "examples"
CARDS = Path(__file__).resolve().parents[2] / "configs" / "v2" / "cards"


def test_example_result_record_validates():
    check(json.loads((EX / "vmmbench_result.json").read_text()), "vmmbench_result")


def test_example_console_summary_validates():
    check(json.loads((EX / "vmconsole.json").read_text()), "vmconsole")


def test_every_frozen_scenario_card_validates():
    cards = sorted(CARDS.glob("*.yaml"))
    assert len(cards) == 16
    for f in cards:
        c = yaml.safe_load(f.read_text())
        c.pop("config_hash", None)
        check(c, "scenario_card")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.pop("metrics"),
        lambda r: r.__setitem__("schema", "vmmbench/2"),
        lambda r: r["budget"].__setitem__("resource", "cpu"),
        lambda r: r["metrics"].__setitem__("missed_failures", 1.5),
        lambda r: r["world"].__setitem__("family", "test-set"),
        lambda r: r["run"].__setitem__("extra", 1),
    ],
)
def test_broken_records_are_rejected(mutate):
    rec = json.loads((EX / "vmmbench_result.json").read_text())
    bad = copy.deepcopy(rec)
    mutate(bad)
    with pytest.raises(ValidationError):
        check(bad, "vmmbench_result")


def test_unknown_schema_keywords_are_refused():
    with pytest.raises(ValidationError):
        validate(1, {"type": "integer", "minimum": 0})
