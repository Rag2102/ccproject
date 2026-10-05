"""Week 25: check downloaded and processed inputs against data/CHECKSUMS.sha256.

Backblaze ZIPs are checked through the SHA-256 the ingest records for each archive
(results/v2/backblaze_archives.csv), because the ingest deletes ZIPs after conversion. Google
2019 shards are checked against the bucket's MD5 at download time (13_trace_rho.py), so they are
not listed here. Exit status 1 if anything differs or is missing.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    want = {}
    for line in (ROOT / "data" / "CHECKSUMS.sha256").read_text().splitlines():
        if line and not line.startswith("#"):
            h, name = line.split(maxsplit=1)
            want[name] = h
    bad, ok = [], 0
    arch = ROOT / "results" / "v2" / "backblaze_archives.csv"
    got = (
        {f"backblaze/{r.archive}.zip": r.zip_sha256 for r in pd.read_csv(arch).itertuples()}
        if arch.exists()
        else {}
    )
    for name, h in want.items():
        if name.startswith("backblaze/"):
            g = got.get(name)
        else:
            p = ROOT / "data" / name
            g = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
        if g == h:
            ok += 1
        else:
            bad.append((name, "missing" if g is None else "differs"))
    print(f"{ok} of {len(want)} match")
    for name, why in bad:
        print(f"  {why}: {name}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
