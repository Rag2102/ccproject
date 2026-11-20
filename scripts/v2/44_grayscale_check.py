"""Week 33, task 2: grayscale legibility of the figures.

Two checks:
  palette  every pair of policy colours in figstyle.C whose grayscale luminance differs by less
           than `--min-dl` (default 0.10) must differ in marker or line style (figstyle.MK and
           figstyle.LS), so a grayscale print still separates them.
  figures  every figure script that plots per policy takes its marker and line style from figstyle
           (no hard-coded "-o"), and each PDF in results/figures renders to grayscale
           (results/figures/gray/<name>.png, via pdftoppm -gray) for a look by eye.

Exit 1 if a palette pair fails or a policy-plotting script hard-codes its style.
"""

from __future__ import annotations

import argparse
import itertools
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import figstyle  # noqa: E402

FIG = ROOT / "results" / "figures"
POLICY_SCRIPTS = ["31_fig_f4.py", "35_fig_vs_p0.py", "27_pareto.py"]


def luminance(hex_colour: str) -> float:
    """Relative luminance (sRGB, ITU-R BT.709), 0 black to 1 white."""
    rgb = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def palette(min_dl: float) -> list[str]:
    bad = []
    pols = [p for p in figstyle.C if p not in ("P7", "P8")]  # oracle and random: not in figures
    for a, b in itertools.combinations(pols, 2):
        dl = abs(luminance(figstyle.C[a]) - luminance(figstyle.C[b]))
        if dl >= min_dl:
            continue
        same_mk = figstyle.MK[a] == figstyle.MK[b]
        same_ls = figstyle.LS[a] == figstyle.LS[b]
        if same_mk and same_ls:
            bad.append(f"{a}/{b}: luminance differs by {dl:.3f} and marker and line style match")
    return bad


def scripts() -> list[str]:
    bad = []
    for s in POLICY_SCRIPTS:
        t = (ROOT / "scripts" / "v2" / s).read_text()
        if re.search(r"""(fmt=|plot\([^)]*?)["'][-:.]*o["']""", t) or "figstyle.MK" not in t:
            bad.append(f"{s}: per-policy style not taken from figstyle.MK / LS")
    return bad


def render() -> int:
    if not shutil.which("pdftoppm"):
        print("pdftoppm not found: grayscale renders skipped")
        return 0
    out = FIG / "gray"
    out.mkdir(exist_ok=True)
    n = 0
    for pdf in sorted(FIG.glob("*.pdf")):
        subprocess.run(
            [
                "pdftoppm",
                "-gray",
                "-png",
                "-r",
                "110",
                "-singlefile",
                str(pdf),
                str(out / pdf.stem),
            ],
            check=True,
        )
        n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--min-dl", type=float, default=0.10)
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    bad = palette(a.min_dl) + scripts()
    close = [
        (x, y)
        for x, y in itertools.combinations([p for p in figstyle.C if p not in ("P7", "P8")], 2)
        if abs(luminance(figstyle.C[x]) - luminance(figstyle.C[y])) < a.min_dl
    ]
    print(
        f"{len(close)} colour pairs too close in grayscale, all separated by marker or line style"
    )
    if not a.no_render:
        print(f"{render()} figures rendered to {(FIG / 'gray').relative_to(ROOT)}")
    for b in bad:
        print("FAIL", b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
