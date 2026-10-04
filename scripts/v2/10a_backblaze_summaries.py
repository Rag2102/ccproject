"""Weeks 4-5: quality checks, group columns, v1 sanity check, AFR, life table, Kaplan-Meier.

Reads the Parquet written by 10_backblaze_ingest.py (every quarter finished so far) and writes

    docs/v2/data_quality_report.md        generated; re-run after the ingest finishes
    results/v2/backblaze_quality.json     every number in the report
    results/v2/backblaze_null_rates.csv   null share per SMART column per model (>= 100k drive-days)
    results/v2/backblaze_archives.csv     archive, size, SHA-256, CSV rows (for data_sources.md)
    results/v2/backblaze_daily.csv        drives and failures per day (date gaps, fleet size)
    results/v2/backblaze_group_sizes.csv  drives per group where group columns exist
    results/v2/backblaze_v1_sanity.json   2013-2017 slice against v1's drive table
    results/v2/afr_by_model_year.csv      drive-days, failures, AFR per model and year
    results/v2/afr_v1_by_model.csv        2013-2017 per-model counts, v2 next to v1
    results/v2/afr_v1_by_age.csv          2013-2017 per-age-bucket counts, v2 next to v1
    data/v2/backblaze/life_table.parquet  one row per drive (not committed; about 30 MB)
    results/figures/v2_{fleet_afr,km_top10,group_sizes}.pdf

Steps are cached per quarter in data/v2/backblaze/cache/, so a re-run only reads new quarters.

Run from the repository root:  .venv/bin/python scripts/v2/10a_backblaze_summaries.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BB = ROOT / "data" / "v2" / "backblaze"
PARQUET, META, CACHE = BB / "parquet", BB / "meta", BB / "cache"
RES, FIG, DOCS = ROOT / "results" / "v2", ROOT / "results" / "figures", ROOT / "docs" / "v2"
V1_DRIVES = ROOT / "data" / "processed" / "backblaze_drives_clean.csv"
V1_BY_MODEL = ROOT / "data" / "processed" / "backblaze_failure_rate_by_model.csv"
V1_BY_AGE = ROOT / "data" / "processed" / "backblaze_failure_rate_by_age.csv"
V1_END = date(2017, 12, 31)
V1_MIN_CAPACITY = 1.5e12  # bytes; smallest drive in v1's table

SMART = [f"smart_{i}_raw" for i in (5, 9, 12, 187, 188, 190, 194, 197, 198, 199)]
# Backblaze writes some models with a vendor prefix ("Hitachi HDS5C3030ALA630"); v1's table
# does not. model_key strips it so the two can be joined.
MODEL_KEY = (
    r"regexp_replace(upper(trim(model)), '^(HGST|HITACHI|TOSHIBA|WDC|SEAGATE|SAMSUNG)\s+', '')"
)
GROUP_COLS = ["datacenter", "cluster_id", "vault_id", "pod_id", "pod_slot_num", "is_legacy_format"]


def quarters() -> list[Path]:
    return sorted(PARQUET.glob("*_Q?.parquet"))


def per_quarter(con: duckdb.DuckDBPyConnection, name: str, sql: str) -> pd.DataFrame:
    """Run sql (with {src} for the quarter) on each quarter, caching each result as Parquet."""
    out = []
    for pq in quarters():
        c = CACHE / name / pq.name
        if not c.exists() or c.stat().st_mtime < pq.stat().st_mtime:
            c.parent.mkdir(parents=True, exist_ok=True)
            src = f"read_parquet('{pq}')"
            con.execute(f"COPY ({sql.format(src=src, q=pq.stem)}) TO '{c}' (FORMAT PARQUET)")
        out.append(c)
    return con.execute(
        f"SELECT * FROM read_parquet({[str(p) for p in out]!r}, union_by_name=true)"
    ).df()


def has_cols(con: duckdb.DuckDBPyConnection, pq: Path) -> set[str]:
    return {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{pq}')").fetchall()}


# --------------------------------------------------------------------------- per-quarter passes


def drive_quarter(con) -> pd.DataFrame:
    """One row per (quarter, serial, model): the input to the life table and several checks."""
    return per_quarter(
        con,
        "drive_quarter",
        f"""SELECT '{{q}}' AS quarter, serial_number, model, {MODEL_KEY} AS model_key,
                   max(capacity_bytes) FILTER (capacity_bytes > 0) AS capacity_bytes,
                   min(date) AS first_seen, max(date) AS last_seen, count(*) AS days,
                   count(DISTINCT date) AS distinct_days,
                   max(failure) AS failed, min(date) FILTER (failure = 1) AS fail_date,
                   sum(failure) AS fail_rows,
                   arg_min(smart_9_raw, date) AS poh_first, arg_max(smart_9_raw, date) AS poh_last
            FROM {{src}} GROUP BY ALL""",
    )


def daily(con) -> pd.DataFrame:
    return per_quarter(
        con,
        "daily",
        "SELECT date, count(*) AS drives, sum(failure) AS failures FROM {src} GROUP BY date",
    )


def model_year(con) -> pd.DataFrame:
    return per_quarter(
        con,
        "model_year",
        f"""SELECT {MODEL_KEY} AS model_key, year(date) AS year, count(*) AS drive_days,
                   sum(failure) AS failures FROM {{src}} GROUP BY ALL""",
    )


def nulls(con) -> pd.DataFrame:
    nn = ", ".join(f"count({c}) AS {c}" for c in SMART)
    return per_quarter(
        con,
        "nulls",
        f"SELECT {MODEL_KEY} AS model_key, count(*) AS n, {nn} FROM {{src}} GROUP BY ALL",
    )


def validity(con) -> pd.DataFrame:
    """Row-level checks that need the whole quarter: duplicates, bad values, power-on hours."""
    return per_quarter(
        con,
        "validity",
        """WITH t AS (
                SELECT serial_number, date, smart_9_raw,
                       lag(smart_9_raw) OVER (PARTITION BY serial_number ORDER BY date) AS prev_poh
                FROM {src})
           SELECT '{q}' AS quarter,
                  (SELECT count(*) FROM {src}) AS rows,
                  (SELECT count(*) FROM (SELECT date, serial_number FROM {src}
                                         GROUP BY ALL HAVING count(*) > 1)) AS dup_keys,
                  (SELECT count(*) FROM {src} WHERE serial_number IS NULL OR serial_number = '')
                      AS null_serial,
                  (SELECT count(*) FROM {src} WHERE model IS NULL OR model = '') AS null_model,
                  (SELECT count(*) FROM {src} WHERE capacity_bytes IS NULL OR capacity_bytes <= 0)
                      AS bad_capacity,
                  (SELECT count(*) FROM {src} WHERE failure IS NULL OR failure NOT IN (0, 1))
                      AS bad_failure,
                  (SELECT count(*) FROM t WHERE smart_9_raw < 0) AS poh_negative,
                  (SELECT count(*) FROM t WHERE smart_9_raw < prev_poh) AS poh_decrease,
                  (SELECT count(*) FROM t WHERE smart_9_raw < prev_poh - 24) AS poh_decrease_gt_24h,
                  (SELECT count(*) FROM t WHERE prev_poh IS NOT NULL) AS poh_pairs""",
    )


# --------------------------------------------------------------------------- derived tables


def life_table(dq: pd.DataFrame) -> pd.DataFrame:
    dq = dq.sort_values(["serial_number", "first_seen"])
    g = dq.groupby("serial_number", sort=False)
    lt = g.agg(
        first_seen=("first_seen", "min"),
        last_seen=("last_seen", "max"),
        days_observed=("days", "sum"),
        failed=("failed", "max"),
        fail_date=("fail_date", "min"),
        fail_rows=("fail_rows", "sum"),
        n_models=("model_key", "nunique"),
        capacity_bytes=("capacity_bytes", "max"),
        poh_first=("poh_first", "first"),
        poh_last=("poh_last", "last"),
    )
    main = dq.loc[
        dq.groupby("serial_number")["days"].idxmax(), ["serial_number", "model", "model_key"]
    ]
    lt = lt.join(main.set_index("serial_number")).reset_index()
    for c in ("first_seen", "last_seen", "fail_date"):
        lt[c] = pd.to_datetime(lt[c])
    lt["age_entry_days"] = lt["poh_first"] / 24
    lt["age_exit_days"] = lt["poh_last"] / 24
    lt["calendar_days"] = (lt["last_seen"] - lt["first_seen"]).dt.days + 1
    return lt


def km_delayed_entry(entry: np.ndarray, exit_: np.ndarray, event: np.ndarray, grid: np.ndarray):
    """Kaplan-Meier with left truncation: a drive is at risk at age t only if entry < t <= exit."""
    ok = np.isfinite(entry) & np.isfinite(exit_) & (exit_ >= entry) & (entry >= 0)
    entry, exit_, event = entry[ok], exit_[ok], event[ok].astype(bool)
    times = np.unique(exit_[event])
    entries, exits = np.sort(entry), np.sort(exit_)
    at_risk = np.searchsorted(entries, times, side="left") - np.searchsorted(
        exits, times, side="left"
    )
    d = np.bincount(np.searchsorted(times, exit_[event]), minlength=len(times))
    surv = np.cumprod(np.where(at_risk > 0, 1 - d / np.maximum(at_risk, 1), 1.0))
    idx = np.searchsorted(times, grid, side="right") - 1
    return np.where(idx >= 0, surv[np.clip(idx, 0, None)], 1.0), int(ok.sum())


def date_gaps(dd: pd.DataFrame) -> dict:
    dd = dd.groupby("date", as_index=False)[["drives", "failures"]].sum().sort_values("date")
    dd["date"] = pd.to_datetime(dd["date"])
    full = pd.date_range(dd["date"].min(), dd["date"].max(), freq="D")
    missing = full.difference(dd["date"])
    med = dd["drives"].rolling(15, center=True, min_periods=5).median()
    drops = dd[dd["drives"] < 0.8 * med]
    return {
        "first_day": str(dd["date"].min().date()),
        "last_day": str(dd["date"].max().date()),
        "days_present": len(dd),
        "days_missing": len(missing),
        "missing_days": [str(d.date()) for d in missing],
        "days_below_80pct_of_rolling_median": [
            {"date": str(r.date.date()), "drives": int(r.drives)} for r in drops.itertuples()
        ],
    }, dd


def group_columns(con) -> tuple[dict, pd.DataFrame]:
    first = {}
    for m in sorted(META.glob("*.json")):
        meta = json.loads(m.read_text())
        for c in meta.get("extra_columns", []):
            first.setdefault(c, [])
            first[c].append(meta["archive"])
    found = {c: {"archives": len(v), "first": v[0], "last": v[-1]} for c, v in first.items()}
    rows = []
    qs = [pq for pq in quarters() if {"pod_id", "vault_id"} & has_cols(con, pq)]
    if qs:
        pq = qs[-1]  # latest quarter that has group columns
        cols = [
            c
            for c in GROUP_COLS
            if c in has_cols(con, pq) and c not in ("pod_slot_num", "is_legacy_format")
        ]
        for level in range(1, len(cols) + 1):
            key = cols[:level]
            df = con.execute(
                f"""SELECT {", ".join(key)}, count(DISTINCT serial_number) AS drives
                    FROM read_parquet('{pq}')
                    WHERE date = (SELECT max(date) FROM read_parquet('{pq}'))
                    GROUP BY ALL"""
            ).df()
            df.insert(0, "level", "/".join(key))
            df.insert(0, "quarter", pq.stem)
            rows.append(df)
    return found, (pd.concat(rows, ignore_index=True) if rows else pd.DataFrame())


def v1_sanity(lt: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    v1 = pd.read_csv(V1_DRIVES)
    v1["model_key"] = v1["model"].str.upper().str.strip()
    s = lt[lt["first_seen"].dt.date <= V1_END].copy()
    s["failed_by_2017"] = (s["fail_date"].notna() & (s["fail_date"].dt.date <= V1_END)).astype(int)
    last = s["last_seen"].clip(upper=pd.Timestamp(V1_END))
    s["calendar_days_2017"] = (last - s["first_seen"]).dt.days + 1
    j = s.merge(v1, on="serial_number", how="outer", suffixes=("", "_v1"), indicator=True)
    both = j[j["_merge"] == "both"]
    res = {
        "v1_drives": len(v1),
        "v1_failures": int(v1["failed"].sum()),
        "v2_drives_2013_2017": len(s),
        "v2_failures_2013_2017": int(s["failed_by_2017"].sum()),
        "drives_gap_pct": round(100 * (len(s) - len(v1)) / len(v1), 3),
        "failures_gap_pct": round(
            100 * (s["failed_by_2017"].sum() - v1["failed"].sum()) / v1["failed"].sum(), 3
        ),
        "serials_in_both": int(len(both)),
        "serials_only_v1": int((j["_merge"] == "right_only").sum()),
        "serials_only_v2": int((j["_merge"] == "left_only").sum()),
        "failed_agree_share": round(float((both["failed_v1"] == both["failed_by_2017"]).mean()), 5)
        if len(both)
        else None,
        "failed_v1_not_v2": int(((both["failed_v1"] == 1) & (both["failed_by_2017"] == 0)).sum()),
        "failed_v2_not_v1": int(((both["failed_v1"] == 0) & (both["failed_by_2017"] == 1)).sum()),
        "model_agree_share": round(float((both["model_key"] == both["model_key_v1"]).mean()), 5)
        if len(both)
        else None,
        "start_equals_first_seen_share": round(
            float((pd.to_datetime(both["start"]) == both["first_seen"]).mean()), 5
        )
        if len(both)
        else None,
    }
    # Which definition is v1's age_days? Compare with the two candidates.
    if len(both):
        for cand in ("calendar_days_2017", "age_exit_days"):
            d = (both["age_days"] - both[cand]).abs()
            res[f"age_days_vs_{cand}_median_abs_diff"] = round(float(d.median()), 3)
            res[f"age_days_vs_{cand}_within_1d_share"] = round(float((d <= 1).mean()), 5)
    # v1's third-party table has no drive under 1.5 TB (boot and laptop drives are absent).
    # With that one filter the slice should reproduce v1's counts.
    big = s[s["capacity_bytes"] >= V1_MIN_CAPACITY]
    extra = big[~big["serial_number"].isin(v1["serial_number"])]
    res |= {
        "v1_filter": f"first seen by {V1_END}, capacity >= {V1_MIN_CAPACITY / 1e12:g} TB",
        "v2_drives_v1_filter": len(big),
        "v2_failures_v1_filter": int(big["failed_by_2017"].sum()),
        "v2_only_after_filter": extra[
            ["serial_number", "model", "capacity_bytes", "failed_by_2017"]
        ]
        .astype(str)
        .to_dict("records"),
        "failed_v1_not_v2_filtered": big.merge(v1, on="serial_number", suffixes=("", "_v1"))
        .query("failed_v1 == 1 and failed_by_2017 == 0")["serial_number"]
        .tolist(),
        "v2_only_below_filter_drives": int((s["capacity_bytes"] < V1_MIN_CAPACITY).sum()),
        "v2_only_below_filter_failures": int(
            s.loc[s["capacity_bytes"] < V1_MIN_CAPACITY, "failed_by_2017"].sum()
        ),
    }
    by = big.groupby("model_key").agg(
        v2_drives=("failed", "size"), v2_failed=("failed_by_2017", "sum")
    )
    v1m = pd.read_csv(V1_BY_MODEL).set_index("model")
    cmp_ = v1m.join(by, how="left").reset_index().rename(columns={"index": "model"})
    cmp_["v2_failure_rate"] = cmp_["v2_failed"] / cmp_["v2_drives"]
    cmp_["drives_ratio"] = cmp_["v2_drives"] / cmp_["n_drives"]
    cmp_["failed_ratio"] = cmp_["v2_failed"] / cmp_["n_failed"]
    # v1's age table: buckets of age_days, which is power-on hours at the last report / 24
    bins = [0, 90, 365, 730, 1095, 1460, 1825, np.inf]
    labels = ["<90d", "90-365d", "1-2y", "2-3y", "3-4y", "4-5y", "5y+"]
    big = big.assign(age_bucket=pd.cut(big["age_exit_days"], bins=bins, labels=labels))
    by_age = big.groupby("age_bucket", observed=True).agg(
        v2_drives=("failed", "size"), v2_failed=("failed_by_2017", "sum")
    )
    age = pd.read_csv(V1_BY_AGE).set_index("age_bucket").join(by_age).reset_index()
    age["drives_diff"] = age["v2_drives"] - age["n_drives"]
    age["failed_diff"] = age["v2_failed"] - age["n_failed"]
    return res, cmp_, age


# --------------------------------------------------------------------------- report


def md_table(df: pd.DataFrame, floatfmt: str = "{:,.4g}") -> str:
    def f(x):
        if isinstance(x, float):
            return "" if np.isnan(x) else floatfmt.format(x)
        if isinstance(x, int | np.integer):
            return f"{x:,}"
        return str(x)

    head = "| " + " | ".join(df.columns) + " |\n| " + " | ".join("---" for _ in df.columns) + " |\n"
    return head + "".join(
        "| " + " | ".join(f(v) for v in r) + " |\n" for r in df.itertuples(index=False)
    )


def write_report(
    q: dict, val: pd.DataFrame, nr: pd.DataFrame, groups: dict, gs: pd.DataFrame
) -> None:
    man = pd.read_csv(BB / "manifest.csv")
    ok = man[man["status"] == "ok"]
    lines = [
        "# Backblaze data quality report",
        "",
        "Generated by `scripts/v2/10a_backblaze_summaries.py`; do not edit by hand. Numbers are in "
        "`results/v2/backblaze_quality.json`.",
        "",
        f"Coverage: {len(ok)} quarters ({ok['quarter'].iloc[0]} to {ok['quarter'].iloc[-1]}), "
        f"{ok['rows'].sum():,} drive-days, {q['drives']:,} drives, "
        f"{q['failures']:,} drives that failed. "
        f"Archives not ingested or with a row-count mismatch: {q['archives_not_ok'] or 'none'}.",
        "",
        "## 1. Row validity (per quarter, summed)",
        "",
        md_table(
            pd.DataFrame(
                {
                    "check": [
                        "duplicate (date, serial) keys",
                        "null or blank serial",
                        "null or blank model",
                        "capacity missing or <= 0",
                        "failure not 0/1",
                        "unparseable dates (rows dropped at ingest)",
                    ],
                    "rows": [
                        int(val["dup_keys"].sum()),
                        int(val["null_serial"].sum()),
                        int(val["null_model"].sum()),
                        int(val["bad_capacity"].sum()),
                        int(val["bad_failure"].sum()),
                        q["unparseable_dates"],
                    ],
                }
            )
        ),
        "Capacity: Backblaze writes -1 when a drive does not report it; the life table takes each "
        "drive's largest positive value.",
        "",
        "## 2. Drives",
        "",
        md_table(
            pd.DataFrame(
                {
                    "check": [
                        "serial numbers seen under more than one model",
                        "drives with more than one failure = 1 row",
                        "drives still reporting after their first failure = 1",
                        "  of which more than 30 days after",
                    ],
                    "drives": [
                        q["serials_multi_model"],
                        q["drives_multi_failure_rows"],
                        q["drives_report_after_failure"],
                        q["drives_report_after_failure_gt30d"],
                    ],
                }
            )
        ),
        "Rule for the life table and labels: a drive fails at its first failure = 1 row; "
        "later rows are dropped. A serial under two models keeps the model it reported on "
        "most days.",
        "",
        "## 3. Power-on hours (SMART 9)",
        "",
        f"Negative values: {int(val['poh_negative'].sum()):,} rows. Day-to-day decreases: "
        f"{int(val['poh_decrease'].sum()):,} of {int(val['poh_pairs'].sum()):,} consecutive pairs "
        f"({100 * val['poh_decrease'].sum() / max(val['poh_pairs'].sum(), 1):.3f}%); "
        f"decreases larger than 24 h: {int(val['poh_decrease_gt_24h'].sum()):,}. "
        "Pairs are within a quarter; the step across a quarter boundary is not checked. "
        "Age features in Week 7 use the running maximum.",
        "",
        "## 4. Date gaps",
        "",
        f"Days {q['dates']['first_day']} to {q['dates']['last_day']}: "
        f"{q['dates']['days_present']:,} present, {q['dates']['days_missing']} missing.",
        "",
        (
            "Missing days: " + ", ".join(q["dates"]["missing_days"]) + "."
            if q["dates"]["missing_days"]
            else ""
        ),
        "",
        "Days with fewer than 80% of the 15-day rolling median of drives reporting: "
        + (
            ", ".join(
                f"{d['date']} ({d['drives']:,})"
                for d in q["dates"]["days_below_80pct_of_rolling_median"]
            )
            or "none"
        )
        + ". A drive absent on such a day is not a failure; labels use the failure flag only.",
        "",
        "## 5. Null share of SMART columns",
        "",
        "Share of drive-days where the raw value is missing, for the 15 models with the most "
        "drive-days (all models with at least 100k drive-days are in "
        "`results/v2/backblaze_null_rates.csv`).",
        "",
        md_table(nr.head(15), "{:.3f}"),
        "## 6. Group columns",
        "",
    ]
    if groups:
        lines.append(md_table(pd.DataFrame([{"column": k, **v} for k, v in groups.items()])))
        if len(gs):
            summ = (
                gs.groupby("level")["drives"]
                .describe(percentiles=[0.5])
                .reset_index()[["level", "count", "min", "50%", "max"]]
            )
            summ.columns = ["level", "groups", "min drives", "median drives", "max drives"]
            lines += [
                f"Drives per group on the last day of {gs['quarter'].iloc[0]} "
                "(`results/v2/backblaze_group_sizes.csv`, figure `v2_group_sizes.pdf`):",
                "",
                md_table(summ),
            ]
    else:
        lines.append("No datacenter, cluster, vault or pod column in any quarter ingested so far.")
    (DOCS / "data_quality_report.md").write_text("\n".join(lines) + "\n")


# --------------------------------------------------------------------------- figures


def fig_fleet_afr(afr: pd.DataFrame) -> None:
    y = afr.groupby("year")[["drive_days", "failures"]].sum()
    y["afr"] = 100 * y["failures"] / (y["drive_days"] / 365)
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.plot(y.index, y["afr"], marker="o")
    ax.set(xlabel="year", ylabel="fleet AFR (%)", title="Backblaze fleet annualised failure rate")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "v2_fleet_afr.pdf")
    plt.close(fig)


def fig_km(lt: pd.DataFrame) -> dict:
    top = lt["model_key"].value_counts().head(10).index
    grid = np.arange(0, 3651, 30)
    fig, ax = plt.subplots(figsize=(6.5, 4))
    out = {}
    for m in top:
        s = lt[lt["model_key"] == m]
        surv, n = km_delayed_entry(
            s["age_entry_days"].to_numpy(float),
            s["age_exit_days"].to_numpy(float),
            s["failed"].to_numpy(),
            grid,
        )
        ax.plot(grid / 365, surv, label=f"{m} (n={n:,})")
        out[m] = {"n": n, "s_1y": float(surv[grid == 360][0]), "s_3y": float(surv[grid == 1080][0])}
    ax.set(
        xlabel="drive age (years, power-on)", ylabel="survival", title="Kaplan-Meier, delayed entry"
    )
    ax.legend(fontsize=6)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "v2_km_top10.pdf")
    plt.close(fig)
    return out


def fig_groups(gs: pd.DataFrame) -> None:
    if gs.empty:
        return
    levels = list(gs["level"].unique())
    fig, axes = plt.subplots(1, len(levels), figsize=(3.2 * len(levels), 3))
    for ax, lv in zip(np.atleast_1d(axes), levels, strict=True):
        ax.hist(gs.loc[gs["level"] == lv, "drives"], bins=30)
        ax.set(title=lv, xlabel="drives per group", ylabel="groups")
    fig.tight_layout()
    fig.savefig(FIG / "v2_group_sizes.pdf")
    plt.close(fig)


# --------------------------------------------------------------------------- main


def main() -> None:
    for d in (CACHE, RES, FIG):
        d.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"SET temp_directory='{BB / 'tmp' / '_duckdb_summ'}'; SET memory_limit='6GB'")
    con.execute("SET preserve_insertion_order=false")
    print(f"{len(quarters())} quarters")

    dq = drive_quarter(con)
    lt = life_table(dq)
    lt.to_parquet(BB / "life_table.parquet", index=False)
    after = lt["fail_date"].notna() & (lt["last_seen"] > lt["fail_date"])
    metas = [json.loads(m.read_text()) for m in sorted(META.glob("*.json"))]
    pd.DataFrame(
        [
            {
                k: m[k]
                for k in (
                    "archive",
                    "url",
                    "zip_bytes",
                    "zip_sha256",
                    "csv_files",
                    "csv_rows",
                    "status",
                )
            }
            for m in metas
        ]
    ).to_csv(RES / "backblaze_archives.csv", index=False)
    gaps, dd = date_gaps(daily(con))
    dd.to_csv(RES / "backblaze_daily.csv", index=False)

    val = validity(con)
    ny = nulls(con).groupby("model_key").sum(numeric_only=True)
    nr = (1 - ny[SMART].div(ny["n"], axis=0)).assign(drive_days=ny["n"])
    nr = nr[nr["drive_days"] >= 100_000].sort_values("drive_days", ascending=False)
    nr = nr.reset_index()[["model_key", "drive_days", *SMART]]
    nr.columns = [c.replace("smart_", "s").replace("_raw", "") for c in nr.columns]
    nr.to_csv(RES / "backblaze_null_rates.csv", index=False)

    groups, gs = group_columns(con)
    gs.to_csv(RES / "backblaze_group_sizes.csv", index=False)

    afr = model_year(con).groupby(["model_key", "year"], as_index=False).sum()
    afr["afr"] = afr["failures"] / (afr["drive_days"] / 365)
    afr.sort_values(["model_key", "year"]).to_csv(RES / "afr_by_model_year.csv", index=False)

    # v1 compares with the 2013-2017 quarters only, so last_seen and age stop at 2017
    sanity, by_model, by_age = v1_sanity(life_table(dq[dq["quarter"] < "2018"]))
    by_model.to_csv(RES / "afr_v1_by_model.csv", index=False)
    by_age.to_csv(RES / "afr_v1_by_age.csv", index=False)
    (RES / "backblaze_v1_sanity.json").write_text(json.dumps(sanity, indent=2))

    q = {
        "quarters": len(quarters()),
        "drive_days": int(val["rows"].sum()),
        "drives": len(lt),
        "failures": int(lt["failed"].sum()),
        "archives_not_ok": [m["archive"] for m in metas if m["status"] != "ok"],
        "unparseable_dates": int(sum(m.get("unparseable_dates", 0) for m in metas)),
        "serials_multi_model": int((lt["n_models"] > 1).sum()),
        "drives_multi_failure_rows": int((lt["fail_rows"] > 1).sum()),
        "drives_report_after_failure": int(after.sum()),
        "drives_report_after_failure_gt30d": int(
            (after & ((lt["last_seen"] - lt["fail_date"]).dt.days > 30)).sum()
        ),
        "validity": {k: int(val[k].sum()) for k in val.columns if k not in ("quarter",)},
        "dates": gaps,
        "group_columns": groups,
        "km": fig_km(lt),
        "v1_sanity": sanity,
    }
    (RES / "backblaze_quality.json").write_text(json.dumps(q, indent=2, default=str))
    write_report(q, val, nr, groups, gs)
    fig_fleet_afr(afr)
    fig_groups(gs)
    print(json.dumps({k: q[k] for k in ("quarters", "drive_days", "drives", "failures")}, indent=1))
    print(json.dumps(sanity, indent=1))


if __name__ == "__main__":
    main()
