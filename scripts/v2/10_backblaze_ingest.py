"""Week 4: Backblaze drive-stats ingest, one archive at a time, CSV -> Parquet.

For every archive on the Backblaze download page (data_2013.zip ... data_Qn_YYYY.zip):

  1. download it (curl, resumable) and record its SHA-256;
  2. extract it to a temporary folder (macOS resource forks skipped);
  3. read every daily CSV with DuckDB as text (union_by_name, so the column set may change
     inside an archive) and cast the kept columns: SMART columns to DOUBLE, never inferred,
     because a column that is empty in its first rows is otherwise mis-typed;
  4. write data/v2/backblaze/parquet/<year>_Q<n>.parquet (annual archives 2013-2015 are split
     into quarters by date);
  5. check that the Parquet row count equals the number of data lines in the CSVs;
  6. delete the extracted CSVs, keep the ZIP (pass --delete-zips to drop it too).

Kept columns: date, serial_number, model, capacity_bytes, failure; SMART 5, 9, 12, 187, 188,
190, 194, 197, 198, 199 (raw and normalized where present); and every other non-SMART column
as text (datacenter, cluster_id, vault_id, pod_id, ... in recent quarters), so the group
columns are found rather than guessed.

Resumable: an archive whose meta/<archive>.json says "ok" and whose Parquet files exist is
skipped. manifest.csv (one row per quarter) is rebuilt from the meta files after each archive.

Run from the repository root:
    nohup .venv/bin/python scripts/v2/10_backblaze_ingest.py --all > logs/ingest.log 2>&1 &
    .venv/bin/python scripts/v2/10_backblaze_ingest.py --only data_Q1_2016   # one archive
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data" / "v2" / "backblaze"
RAW, TMP, PARQUET, META = BASE / "raw", BASE / "tmp", BASE / "parquet", BASE / "meta"
PAGE = "https://www.backblaze.com/cloud-storage/resources/hard-drive-test-data"
URL_RE = re.compile(
    r"https://f001\.backblazeb2\.com/file/Backblaze-Hard-Drive-Data/(data_[0-9A-Za-z_]+)\.zip"
)

BASE_COLS = ["date", "serial_number", "model", "capacity_bytes", "failure"]
SMART_IDS = [5, 9, 12, 187, 188, 190, 194, 197, 198, 199]
SMART_COLS = [f"smart_{i}_{kind}" for i in SMART_IDS for kind in ("raw", "normalized")]
# Bump when conversion changes; archives converted by an older version are redone (from the ZIP).
# 2: M/D/YY dates and CR-only line endings handled (2018-02-25.csv).
META_VERSION = 2


def log(msg: str) -> None:
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def list_archives() -> list[str]:
    """Archive names from the download page, oldest first."""
    # curl, not urllib: the page answers 403 to Python's default client
    r = subprocess.run(["curl", "-fsSL", PAGE], check=True, capture_output=True, text=True)
    html = r.stdout
    names = sorted(set(URL_RE.findall(html)), key=archive_order)
    if not names:
        sys.exit("no archive links found on the download page; has it changed?")
    return names


def archive_order(name: str) -> tuple[int, int]:
    m = re.fullmatch(r"data_(\d{4})", name)
    if m:
        return int(m.group(1)), 0
    m = re.fullmatch(r"data_Q(\d)_(\d{4})", name)
    if not m:
        raise ValueError(f"unexpected archive name {name}")
    return int(m.group(2)), int(m.group(1))


def quarters_of(name: str) -> list[tuple[int, int]]:
    year, q = archive_order(name)
    return [(year, k) for k in (1, 2, 3, 4)] if q == 0 else [(year, q)]


def url_of(name: str) -> str:
    return f"https://f001.backblazeb2.com/file/Backblaze-Hard-Drive-Data/{name}.zip"


def download(name: str) -> Path:
    """Resumable download; the .part file is renamed only after curl succeeds."""
    dst = RAW / f"{name}.zip"
    if dst.exists():
        return dst
    part = dst.with_suffix(".zip.part")
    for attempt in range(1, 6):
        r = subprocess.run(
            ["curl", "-fsSL", "--retry", "5", "--retry-delay", "10", "-C", "-"]
            + ["-o", str(part), url_of(name)],
            check=False,
        )
        if r.returncode == 0:
            break
        log(f"{name}: curl exit {r.returncode}, attempt {attempt}")
        time.sleep(30 * attempt)
    else:
        raise RuntimeError(f"{name}: download failed")
    with zipfile.ZipFile(part) as z:  # a truncated ZIP fails here, before it is trusted
        bad = z.testzip()
        if bad:
            raise RuntimeError(f"{name}: corrupt member {bad}")
    part.rename(dst)
    return dst


def extract(name: str, zpath: Path) -> list[Path]:
    out = TMP / name
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    with zipfile.ZipFile(zpath) as z:
        members = [
            m
            for m in z.namelist()
            if m.endswith(".csv") and "__MACOSX" not in m and not Path(m).name.startswith("._")
        ]
        z.extractall(out, members)
    return sorted(out.rglob("*.csv"))


def data_lines(path: Path) -> int:
    """Data lines after the header; a last line without a terminator counts, blank end lines do not.

    Lines end in LF (or CRLF), except a few files saved with old Mac CR-only endings
    (2018-02-25.csv is one): those are counted by CR.
    """
    lf = cr = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            lf += chunk.count(b"\n")
            cr += chunk.count(b"\r")
    term, other = (b"\n", b"\r") if lf or not cr else (b"\r", b"\n")
    n = max(lf, cr) if term == b"\r" else lf
    with path.open("rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - 64))
        tail = f.read().replace(other, b"")
    if not tail.endswith(term):
        n += 1  # last line has no terminator
    else:
        tail = tail[:-1]
    n -= len(tail) - len(tail.rstrip(term))  # blank lines at the end are not rows
    return n - 1


def select_list(cols: list[str]) -> tuple[str, list[str]]:
    lower = {c.lower(): c for c in cols}
    missing = [c for c in BASE_COLS if c not in lower]
    if missing:
        raise RuntimeError(f"base columns missing: {missing}")
    parts = [
        # ISO dates, except a few files written as M/D/YY (2018-02-25.csv); checked against
        # the date in the file name (date_vs_filename_mismatch in the meta file)
        f"COALESCE(TRY_CAST({q(lower['date'])} AS DATE), "
        f"TRY_STRPTIME({q(lower['date'])}, '%m/%d/%y')::DATE, "
        f"TRY_STRPTIME({q(lower['date'])}, '%m/%d/%Y')::DATE) AS date",
        "TRY_CAST(regexp_extract(filename, '(\\d{4}-\\d{2}-\\d{2})\\.csv$', 1) AS DATE)"
        " AS file_date",
        f"TRY_CAST({q(lower['date'])} AS DATE) IS NULL AS alt_date_format",
        f"{q(lower['serial_number'])} AS serial_number",
        f"TRIM({q(lower['model'])}) AS model",
        f"TRY_CAST({q(lower['capacity_bytes'])} AS BIGINT) AS capacity_bytes",
        f"TRY_CAST({q(lower['failure'])} AS TINYINT) AS failure",
    ]
    for c in SMART_COLS:
        cast = f"TRY_CAST({q(lower[c])} AS DOUBLE)" if c in lower else "NULL::DOUBLE"
        parts.append(f"{cast} AS {c}")
    extras = [
        lower[c]
        for c in sorted(lower)
        if c not in BASE_COLS and not c.startswith("smart_") and c != "filename"
    ]
    parts += [f"NULLIF(TRIM({q(c)}), '') AS {q(c.lower())}" for c in extras]
    return ", ".join(parts), [c.lower() for c in extras]


def q(col: str) -> str:
    return '"' + col.replace('"', '""') + '"'


def convert(name: str, files: list[Path], con: duckdb.DuckDBPyConnection) -> dict:
    opts = "union_by_name=true, all_varchar=true, header=true, filename=true"
    src = f"read_csv({[str(f) for f in files]!r}, {opts})"
    cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()]
    sel, extras = select_list(cols)
    con.execute(f"CREATE OR REPLACE TEMP VIEW v AS SELECT {sel} FROM {src}")
    bad_dates, alt_format, vs_file = con.execute(
        "SELECT count(*) FILTER (date IS NULL), "
        "count(*) FILTER (alt_date_format AND date IS NOT NULL), "
        "count(*) FILTER (date <> file_date) FROM v"
    ).fetchone()
    # A row dated differently from its file is dropped when the correctly named file has the
    # same (date, serial): 2022-12-10.csv holds an exact copy of 2022-12-11 (power-on hours
    # equal), so that day would otherwise count twice. Archives without such rows are unchanged.
    dup_dropped = 0
    if vs_file:
        con.execute(
            """CREATE OR REPLACE TEMP VIEW k AS SELECT * FROM v
               WHERE NOT (date <> file_date AND (date, serial_number) IN
                          (SELECT date, serial_number FROM v WHERE date = file_date))"""
        )
        dup_dropped = (
            vs_file - con.execute("SELECT count(*) FROM k WHERE date <> file_date").fetchone()[0]
        )
    else:
        con.execute("CREATE OR REPLACE TEMP VIEW k AS SELECT * FROM v")
    out = []
    for year, qn in quarters_of(name):
        pq = PARQUET / f"{year}_Q{qn}.parquet"
        where = f"year(date) = {year} AND quarter(date) = {qn}"
        n = con.execute(f"SELECT count(*) FROM k WHERE {where}").fetchone()[0]
        if n == 0:
            log(f"{name}: no rows for {year}_Q{qn}")
            continue
        tmp = pq.with_suffix(".parquet.part")
        con.execute(
            f"COPY (SELECT * EXCLUDE (file_date, alt_date_format) FROM k WHERE {where} "
            f"ORDER BY date, serial_number) TO '{tmp}' "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        tmp.rename(pq)
        rows, fails, drives, dmin, dmax, days = con.execute(
            "SELECT count(*), sum(failure), count(DISTINCT serial_number), min(date), max(date), "
            f"count(DISTINCT date) FROM read_parquet('{pq}')"
        ).fetchone()
        out.append(
            {
                "quarter": f"{year}_Q{qn}",
                "rows": rows,
                "failures": int(fails or 0),
                "drives": drives,
                "date_min": str(dmin),
                "date_max": str(dmax),
                "days": days,
                "parquet_bytes": pq.stat().st_size,
                "parquet_sha256": sha256(pq),
            }
        )
    schema = sorted(c.lower() for c in cols)
    return {
        "csv_columns": len(cols),
        "schema_sha256": hashlib.sha256("\n".join(schema).encode()).hexdigest()[:16],
        "extra_columns": extras,
        "smart_present": [c for c in SMART_COLS if c in schema],
        "unparseable_dates": bad_dates,
        "rows_with_mdy_dates": alt_format,
        "date_vs_filename_mismatch": vs_file,
        "duplicate_rows_dropped": dup_dropped,
        "quarters": out,
    }


def process(name: str, zpath: Path, delete_zips: bool) -> dict:
    t0 = time.time()
    files = extract(name, zpath)
    csv_rows = sum(data_lines(f) for f in files)
    con = duckdb.connect()
    con.execute(f"SET temp_directory='{TMP / '_duckdb'}'; SET memory_limit='6GB'")
    con.execute("SET preserve_insertion_order=false")
    try:
        res = convert(name, files, con)
    finally:
        con.close()
    pq_rows = sum(x["rows"] for x in res["quarters"])
    meta = {
        "meta_version": META_VERSION,
        "archive": name,
        "url": url_of(name),
        "zip_bytes": zpath.stat().st_size,
        "zip_sha256": sha256(zpath),
        "csv_files": len(files),
        "csv_rows": csv_rows,
        "parquet_rows": pq_rows,
        "rows_match": csv_rows
        == pq_rows + res["unparseable_dates"] + res["duplicate_rows_dropped"],
        **res,
        "processed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "seconds": round(time.time() - t0, 1),
    }
    meta["status"] = "ok" if meta["rows_match"] else "row_mismatch"
    shutil.rmtree(TMP / name, ignore_errors=True)
    if delete_zips:
        zpath.unlink()
    (META / f"{name}.json").write_text(json.dumps(meta, indent=2))
    return meta


def done(name: str) -> bool:
    m = META / f"{name}.json"
    if not m.exists():
        return False
    meta = json.loads(m.read_text())
    files = [PARQUET / f"{x['quarter']}.parquet" for x in meta["quarters"]]
    current = meta.get("meta_version") == META_VERSION
    return current and meta.get("status") == "ok" and all(f.exists() for f in files)


def write_manifest() -> None:
    rows = []
    for m in sorted(META.glob("*.json"), key=lambda p: archive_order(p.stem)):
        meta = json.loads(m.read_text())
        for x in meta["quarters"]:
            rows.append(
                {
                    "quarter": x["quarter"],
                    "archive": meta["archive"],
                    "status": meta["status"],
                    "rows": x["rows"],
                    "failures": x["failures"],
                    "drives": x["drives"],
                    "date_min": x["date_min"],
                    "date_max": x["date_max"],
                    "days": x["days"],
                    "parquet_sha256": x["parquet_sha256"],
                    "zip_sha256": meta["zip_sha256"],
                    "zip_bytes": meta["zip_bytes"],
                    "schema_sha256": meta["schema_sha256"],
                    "csv_columns": meta["csv_columns"],
                }
            )
    if rows:
        with (BASE / "manifest.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="every archive on the download page")
    g.add_argument("--only", nargs="+", metavar="ARCHIVE", help="e.g. data_2013 data_Q1_2016")
    ap.add_argument("--delete-zips", action="store_true", help="delete each ZIP after conversion")
    ap.add_argument("--downloads", type=int, default=3, help="parallel downloads (default 3)")
    ap.add_argument("--force", action="store_true", help="re-convert even if already done")
    args = ap.parse_args()

    for d in (RAW, TMP, PARQUET, META):
        d.mkdir(parents=True, exist_ok=True)
    names = list_archives() if args.all else sorted(args.only, key=archive_order)
    todo = names if args.force else [n for n in names if not done(n)]
    log(f"{len(names)} archives, {len(names) - len(todo)} already done, {len(todo)} to do")

    failed = []
    with ThreadPoolExecutor(max_workers=args.downloads) as pool:
        futures = {n: pool.submit(download, n) for n in todo}
        for n in todo:  # downloads run ahead; conversion is in order, one archive at a time
            try:
                zpath = futures[n].result()
                meta = process(n, zpath, args.delete_zips)
                log(
                    f"{n}: {meta['status']} rows={meta['parquet_rows']:,} csv={meta['csv_rows']:,} "
                    f"quarters={len(meta['quarters'])} {meta['seconds']}s"
                )
                if meta["status"] != "ok":
                    failed.append(n)
            except Exception as e:  # one bad archive must not stop the run; re-run with --only
                log(f"{n}: FAILED {type(e).__name__}: {e}")
                shutil.rmtree(TMP / n, ignore_errors=True)
                failed.append(n)
            write_manifest()
    log(f"finished; failed or mismatched: {failed or 'none'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
