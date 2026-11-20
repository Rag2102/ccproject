"""Week 24: compare two copies of a generated table (Table 3 CSV): identical, or which cells differ
and by how much (every number in a cell is compared; display rounding is 0.1 point)."""

from __future__ import annotations

import re
import sys

import pandas as pd

NUM = re.compile(r"[-+]?\d+\.\d+|[-+]?\d+")


def main(a: str, b: str) -> None:
    x, y = pd.read_csv(a, dtype=str), pd.read_csv(b, dtype=str)
    if list(x.columns) != list(y.columns) or len(x) != len(y):
        sys.exit(f"shape differs: {x.shape} vs {y.shape}")
    diffs, worst = [], 0.0
    for i in range(len(x)):
        for c in x.columns:
            u, v = str(x.at[i, c]), str(y.at[i, c])
            if u == v:
                continue
            nu, nv = [float(t) for t in NUM.findall(u)], [float(t) for t in NUM.findall(v)]
            d = max((abs(p - q) for p, q in zip(nu, nv, strict=False)), default=float("inf"))
            worst = max(worst, d)
            diffs.append((x.iat[i, 0], x.iat[i, 1], c, u, v))
    if not diffs:
        print(f"identical: {len(x)} rows x {len(x.columns)} columns")
        return
    print(f"{len(diffs)} cells differ; largest numeric difference {worst:g}")
    for d in diffs[:20]:
        print("  ", *d)
    sys.exit(1)


if __name__ == "__main__":
    main(*sys.argv[1:3])
