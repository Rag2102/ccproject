"""Shared figure style (plan Week 22, task 5): Okabe-Ito palette, >= 8 pt at print size, vector
PDF with embedded TrueType fonts. Every figure script calls apply() and takes colours from C."""

from __future__ import annotations

# Okabe & Ito (2008) colour-blind-safe palette, one fixed colour per policy across all figures
OKABE_ITO = {
    "black": "#000000", "orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73",
    "yellow": "#F0E442", "blue": "#0072B2", "vermillion": "#D55E00", "purple": "#CC79A7",
    "grey": "#999999",
}  # fmt: skip
C = {
    "P0": OKABE_ITO["grey"], "P1": OKABE_ITO["purple"], "P2": OKABE_ITO["vermillion"],
    "P3": OKABE_ITO["orange"], "P4": OKABE_ITO["green"], "P5": OKABE_ITO["blue"],
    "P6": OKABE_ITO["sky"], "P7": OKABE_ITO["black"], "P8": "#BBBBBB",
    "P0+avoid": OKABE_ITO["purple"],  # ADR-010, exploratory (P1 is in no figure)
}  # fmt: skip
# Week 33: a marker and a line style per policy as well, so the figures read in grayscale
# (several Okabe-Ito colours have nearly the same luminance; 44_grayscale_check.py)
MK = {
    "P0": "x",
    "P1": "+",
    "P2": "v",
    "P3": "D",
    "P4": "o",
    "P5": "s",
    "P6": "^",
    "P7": "*",
    "P8": ".",
    "P0+avoid": "P",
}
LS = {
    "P0": ":", "P1": ":", "P2": ":", "P3": "-.", "P4": "-", "P5": "--",
    "P6": (0, (3, 1, 1, 1)), "P7": "-", "P8": ":", "P0+avoid": (0, (5, 2)),
}  # fmt: skip
COLUMN_WIDTH_IN = 3.33  # ACM sigconf single column
TEXT_WIDTH_IN = 7.0


def apply() -> None:
    import matplotlib as mpl

    mpl.rcParams.update(
        {
            "font.size": 8.5,
            "axes.titlesize": 9,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "pdf.fonttype": 42,  # TrueType: editable, embedded, accepted by ACM
            "ps.fonttype": 42,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "lines.linewidth": 1.4,
            "savefig.bbox": "tight",
            "savefig.format": "pdf",
            "axes.prop_cycle": mpl.cycler(color=list(C.values())),
        }
    )
