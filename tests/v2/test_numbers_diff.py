"""scripts/v2/42_numbers_diff.py: changed, filled, added and removed macros are told apart."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "numbers_diff", Path(__file__).resolve().parents[2] / "scripts/v2/42_numbers_diff.py"
)
nd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nd)


def test_diff_kinds():
    old = {"VA": "1.5", "VB": nd.PLACEHOLDER, "VC": "x", "VGone": "3", "VSame": "7"}
    new = {"VA": "2.0", "VB": "+0.4", "VC": "y", "VNew": "1{,}000", "VSame": "7"}
    d = nd.diff(old, new)
    assert d["changed"] == [("VA", "1.5", "2.0", 0.5), ("VC", "x", "y", None)]
    assert d["filled"] == [("VB", "+0.4")]
    assert d["added"] == [("VNew", "1{,}000")]
    assert d["removed"] == [("VGone", "3")]


def test_number_parses_tex_thousands_and_percent():
    assert nd.number("1{,}000") == 1000
    assert nd.number("+3.4\\%") == 3.4
    assert nd.number("C0") is None
