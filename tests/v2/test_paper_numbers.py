"""Week 22: every \\V macro the paper uses is defined by scripts/v2/40_numbers.py."""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("nums", ROOT / "scripts/v2/40_numbers.py")
nums = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nums)


def used_macros() -> set[str]:
    tex = [ROOT / "paper" / "main.tex", *sorted((ROOT / "paper" / "sections").glob("*.tex"))]
    out = set()
    for f in tex:
        body = "\n".join(line.split("%", 1)[0] for line in f.read_text().splitlines())
        out |= set(re.findall(r"\\(V[A-Z][A-Za-z]*)", body))
    return out


def test_every_used_macro_is_defined():
    defined, _ = nums.build()
    missing = used_macros() - set(defined)
    assert not missing, f"paper uses undefined number macros: {sorted(missing)}"


def test_macro_names_are_valid_and_digits_spelled_out():
    assert nums.name("Delta", "P4", "B1", "2") == "VDeltaPFourBOneTwo"
    v, _ = nums.build()
    assert "\\newcommand{\\VHosts}" in nums.render(v)
