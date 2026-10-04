"""Week 7: drive-day features and labels for the temporal hazard model (docs/v2/label_spec.md).

For every drive-day in [--start, --end] (default: the last three years of data):

  features  log1p of SMART 5, 187, 188, 197, 198 and their 7- and 30-day deltas and 30-day
            maxima; age (power-on days, 30-day running maximum); temperature (SMART 194) and
            its 30-day maximum; days since SMART 5 / 197 first became non-zero; model;
            capacity; a missing flag per SMART column. Every window is trailing: it ends on
            the prediction day d and never looks past it.
  labels    y7, y14, y30 = the drive fails within H days after d; ok7, ok14, ok30 = the label
            is decided (not censored by the end of the drive's record). The failure day itself
            and later rows are dropped.

Sampling (to keep the table small): every drive-day within 30 days before a failure is kept
(weight 1); other drive-days are kept with probability 2%, chosen by a hash of (serial, date),
with weight 50. Weights are inverse sampling probabilities, so weighted sums estimate
full-population sums; they are not class weights.

Writes data/v2/features/<year>_Q<n>.parquet (not committed).

Run from the repository root:  .venv/bin/python scripts/v2/11_features.py
"""

from __future__ import annotations

import argparse
import time
from datetime import date, timedelta
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
PARQUET = ROOT / "data" / "v2" / "backblaze" / "parquet"
OUT = ROOT / "data" / "v2" / "features"
SMART_LOG = [5, 187, 188, 197, 198]
KEEP_PER_MILLE = 20  # 2% of drive-days far from a failure
LOOKBACK = 35  # days of history read before each quarter (covers the 30-day windows)
MODEL_KEY = (
    r"regexp_replace(upper(trim(model)), '^(HGST|HITACHI|TOSHIBA|WDC|SEAGATE|SAMSUNG)\s+', '')"
)


def quarter_files() -> list[Path]:
    return sorted(PARQUET.glob("*_Q?.parquet"))


def quarter_range(p: Path) -> tuple[date, date]:
    y, q = int(p.stem[:4]), int(p.stem[-1])
    start = date(y, 3 * (q - 1) + 1, 1)
    end = date(y + (q == 4), 1 if q == 4 else 3 * q + 1, 1) - timedelta(days=1)
    return start, end


def drive_table(con: duckdb.DuckDBPyConnection) -> None:
    """Per drive: first failure day, last day, first non-zero SMART 5 and 197 (all data).

    Aggregated one quarter at a time and then merged: a single pass over all 45 quarters
    exceeds the memory cap on this machine.
    """
    con.execute(
        "CREATE OR REPLACE TABLE dq (serial_number VARCHAR, fail_date DATE, last_seen DATE, "
        "first_nz5 DATE, first_nz197 DATE)"
    )
    for p in quarter_files():
        con.execute(
            f"""INSERT INTO dq
                SELECT serial_number,
                       min(date) FILTER (failure = 1),
                       max(date),
                       min(date) FILTER (smart_5_raw > 0),
                       min(date) FILTER (smart_197_raw > 0)
                FROM read_parquet('{p}')
                GROUP BY serial_number"""
        )
    con.execute(
        """CREATE OR REPLACE TABLE drives AS
           SELECT serial_number, min(fail_date) AS fail_date, max(last_seen) AS last_seen,
                  min(first_nz5) AS first_nz5, min(first_nz197) AS first_nz197
           FROM dq GROUP BY serial_number"""
    )
    con.execute("DROP TABLE dq")
    # a drive that fails: its record ends at the failure (rows after it are dropped)
    con.execute(
        "UPDATE drives SET last_seen = fail_date "
        "WHERE fail_date IS NOT NULL AND last_seen > fail_date"
    )


def features_sql(src: str, q_start: date, q_end: date) -> str:
    def w(days: int) -> str:
        return (
            f"OVER (PARTITION BY d.serial_number ORDER BY d.date "
            f"RANGE BETWEEN INTERVAL {days} DAYS PRECEDING AND CURRENT ROW)"
        )

    cols = []
    for i in SMART_LOG:
        x = f"ln(1 + greatest(d.smart_{i}_raw, 0))"
        cols += [
            f"{x} AS s{i}",
            f"{x} - first_value({x}) {w(7)} AS s{i}_d7",
            f"{x} - first_value({x}) {w(30)} AS s{i}_d30",
            f"max({x}) {w(30)} AS s{i}_max30",
            f"(d.smart_{i}_raw IS NULL)::TINYINT AS s{i}_missing",
        ]
    cols += [
        f"max(d.smart_9_raw) {w(30)} / 24 AS age_days",
        "(d.smart_9_raw IS NULL)::TINYINT AS s9_missing",
        "d.smart_194_raw AS temp",
        f"max(d.smart_194_raw) {w(30)} AS temp_max30",
        "(d.smart_194_raw IS NULL)::TINYINT AS s194_missing",
        "CASE WHEN v.first_nz5 <= d.date THEN d.date - v.first_nz5 END AS days_since_nz5",
        "CASE WHEN v.first_nz197 <= d.date THEN d.date - v.first_nz197 END AS days_since_nz197",
    ]
    labels = []
    for h in (7, 14, 30):
        labels += [
            f"(v.fail_date IS NOT NULL AND v.fail_date - d.date <= {h})::TINYINT AS y{h}",
            f"(v.fail_date IS NOT NULL OR d.date <= v.last_seen - {h})::TINYINT AS ok{h}",
        ]
    near = "(fail_date IS NOT NULL AND fail_date - date <= 30)"
    keep = f"{near} OR hash(serial_number, date) % 1000 < {KEEP_PER_MILLE}"
    return f"""
        WITH f AS (
            SELECT d.date, d.serial_number, {MODEL_KEY} AS model_key,
                   d.capacity_bytes / 1e12 AS capacity_tb,
                   {", ".join(cols)},
                   {", ".join(labels)},
                   v.fail_date
            FROM {src} d JOIN drives v USING (serial_number)
            WHERE d.date < coalesce(v.fail_date, DATE '9999-12-31')
               OR d.date = v.fail_date)
        SELECT *, CASE WHEN {near} THEN 1.0 ELSE {1000 / KEEP_PER_MILLE} END AS w
        FROM f
        WHERE date BETWEEN DATE '{q_start}' AND DATE '{q_end}'
          AND (fail_date IS NULL OR date < fail_date)
          AND ({keep})"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--start", type=date.fromisoformat, help="default: 3 years before the last day")
    ap.add_argument("--end", type=date.fromisoformat, help="default: the last day in the data")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"SET temp_directory='{OUT / '_duckdb'}'; SET memory_limit='8GB'; SET threads=4")
    con.execute("SET preserve_insertion_order=false")
    t0 = time.time()
    drive_table(con)
    last = con.execute("SELECT max(last_seen) FROM drives").fetchone()[0]
    end = args.end or last
    start = args.start or date(end.year - 3, end.month, end.day) + timedelta(days=1)
    print(f"drives table {time.time() - t0:.0f}s; period {start} to {end}", flush=True)
    files = quarter_files()
    for i, p in enumerate(files):
        qs, qe = quarter_range(p)
        qs, qe = max(qs, start), min(qe, end)
        if qs > qe:
            continue
        srcs = [str(p)] + ([str(files[i - 1])] if i > 0 else [])  # previous quarter: lookback
        src = (
            f"(SELECT * FROM read_parquet({srcs!r}, union_by_name=true) "
            f"WHERE date >= DATE '{qs - timedelta(days=LOOKBACK)}' AND date <= DATE '{qe}')"
        )
        t = time.time()
        con.execute(
            f"COPY ({features_sql(src, qs, qe)}) TO '{OUT / p.name}' "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        n, pos = con.execute(
            f"SELECT count(*), sum(y30) FROM read_parquet('{OUT / p.name}')"
        ).fetchone()
        print(
            f"{p.stem}: {n:,} rows, {int(pos or 0):,} y30 = 1, {time.time() - t:.0f}s", flush=True
        )


if __name__ == "__main__":
    main()
