"""The Azure VM columns vmsim uses, as a small committed Parquet (CI without Git LFS).

data/processed/azure_vms_clean.csv.gz (156 MB) is in Git LFS, so a checkout without LFS sees a
pointer file and every simulator test fails. vmsim reads only memory_gb, vcores, avg_cpu,
criticality_weight (as tier) and lifetime_s. This writes exactly those, for every row in file
order with the same dtypes, to data/processed/azure_vms_vmsim.parquet (about 18 MB, zstd), and
checks that the round trip is exact. vmsim.entities.azure_table() reads the extract.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmsim import entities  # noqa: E402


def main() -> None:
    t = entities.azure_table_from_csv()
    out = entities.AZURE_EXTRACT
    t.to_parquet(out, compression="zstd", compression_level=19, index=False)
    back = pd.read_parquet(out)
    assert list(back.columns) == list(t.columns)
    for c in t.columns:
        assert back[c].dtype == t[c].dtype, c
        assert np.array_equal(back[c].to_numpy(), t[c].to_numpy()), c
    print(out, f"{out.stat().st_size / 1e6:.1f} MB", hashlib.sha256(out.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
