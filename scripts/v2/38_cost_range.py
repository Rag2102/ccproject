"""ADR-009, Week 29 task 3: derive the published migration-cost range (G0-low, G0-high).

Reads configs/v2/cost_range.yaml, applies its written rule to every source with status
"extracted" and, when at least `MIN_SOURCES` are extracted, writes the `settings` block back:

  G0-low   highest usable share, lowest dirty rate, shortest downtime   (cheap migration)
  G0-high  lowest usable share, highest dirty rate, longest downtime    (expensive migration)

each value with the source it came from. Without enough sources it prints what is missing and
leaves `settings` null, so scenarios.cost_setting() keeps refusing to run.

  .venv/bin/python scripts/v2/38_cost_range.py           # derive and write
  .venv/bin/python scripts/v2/38_cost_range.py --check   # print only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / "configs" / "v2" / "cost_range.yaml"
MIN_SOURCES = 4
# summary key -> (setting field, unit factor to the simulator's unit)
FIELDS = {
    "usable_share": ("usable_share", 1.0),
    "dirty_mbps": ("dirty_mbps_at_100pct_cpu", 1.0),
    "blackout_s": ("blackout_converged_s", 1.0),
}


def derive(sources: list[dict]) -> tuple[dict | None, list[str]]:
    done = [s for s in sources if s.get("status") == "extracted" and s.get("summary")]
    missing = [s["key"] for s in sources if s not in done]
    if len(done) < MIN_SOURCES:
        return None, missing
    out = {"G0-low": {}, "G0-high": {}}
    for key, (field, f) in FIELDS.items():
        vals = [(v * f, s["key"]) for s in done for v in s["summary"].get(key, [])]
        lo, hi = min(vals), max(vals)
        cheap, dear = (hi, lo) if key == "usable_share" else (lo, hi)
        out["G0-low"][field] = round(cheap[0], 4)
        out["G0-low"][field + "_from"] = cheap[1]
        out["G0-high"][field] = round(dear[0], 4)
        out["G0-high"][field + "_from"] = dear[1]
    return out, missing


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="print only; do not write")
    a = ap.parse_args()
    text = FILE.read_text()
    d = yaml.safe_load(text)
    settings, missing = derive(d["sources"])
    n = len(d["sources"]) - len(missing)
    print(f"{n} of {len(d['sources'])} sources extracted; pending: {', '.join(missing) or 'none'}")
    if settings is None:
        print(f"need at least {MIN_SOURCES}; settings stay null")
        sys.exit(0 if a.check else 1)
    for k, v in settings.items():
        print(k, {f: v[f] for f in v if not f.endswith("_from")})
    if a.check:
        return
    head = text[: text.index("\nsettings:")]
    block = yaml.safe_dump({"settings": settings}, sort_keys=False)
    FILE.write_text(head + "\n" + block)
    print(f"-> {FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
