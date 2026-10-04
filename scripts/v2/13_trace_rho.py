"""Week 8: empirical rho from the Google 2019 trace (cells a, b, h), as fixed in rho_definition.md.

Stage 1, per cell (`--cell a`):
  download machine_events, machine_attributes and instance_events from the public bucket
  gs://clusterdata_2019_<cell>/ (Parquet; MD5 checked against the bucket listing), turn task
  events into placements (SCHEDULE -> next end event of the same task), count placements and
  resident hours per (window, machine, priority tier, scheduling class), then delete the
  instance_events shards (pass --keep-raw to keep them).

Stage 2 (`--analyse`), all aggregated cells:
  risk proxies from machine events (platform long-removal rate, primary; shrunk machine rate;
  all-removals rate), Kendall tau-b and tie-corrected Spearman per window, 2,000-resample
  cluster bootstrap over machines (BCa with a grouped jackknife), dispersion (Gini), the
  provisional mapping to the latent rho_L, and the G1 class per cell.

Writes data/v2/google/cell_<c>/placements.parquet and machines.parquet (not committed),
results/v2/trace_rho.json, results/v2/trace_rho_table.csv, results/figures/v2_trace_rho.pdf.

Run from the repository root:
    .venv/bin/python scripts/v2/13_trace_rho.py --cell a      # then b, h
    .venv/bin/python scripts/v2/13_trace_rho.py --analyse
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import ssl
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import certifi
import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
GOOGLE = ROOT / "data" / "v2" / "google"
RES, FIG = ROOT / "results" / "v2", ROOT / "results" / "figures"
CELLS = ["a", "b", "h"]  # chosen before any data: most production, most beb, most mid-tier work
TABLES = ["machine_events", "machine_attributes", "instance_events"]

US = 1_000_000
DAY = 86_400 * US
T0 = 600 * US  # trace window start (times are offset by 600 s)
T1 = T0 + 31 * DAY
MAXINT = 2**63 - 1
WINDOWS = {2: (8, 14), 3: (15, 21), 4: (22, 28)}  # days; window 1 (days 1-7) is warm-up only
LONG_REMOVAL = DAY  # REMOVE not followed by ADD within 24 h

N_BOOT = 2_000
SEED = 20261004
P_H = 0.30  # provisional break-even, on v1's axis (tie-corrected Spearman, v1 margins)
P_C0 = 0.20  # C0 / C1 boundary, same axis


def log(msg: str) -> None:
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


# --------------------------------------------------------------------------- stage 1: download


def listing(cell: str) -> list[dict]:
    ctx = ssl.create_default_context(cafile=certifi.where())
    out, tok = [], None
    while True:
        u = (
            f"https://storage.googleapis.com/storage/v1/b/clusterdata_2019_{cell}/o"
            "?fields=items(name,size,md5Hash),nextPageToken&maxResults=1000"
            + (f"&pageToken={tok}" if tok else "")
        )
        with urllib.request.urlopen(u, context=ctx, timeout=60) as r:
            d = json.load(r)
        out += [
            it
            for it in d.get("items", [])
            if ".parquet" in it["name"] and it["name"].split("-")[0] in TABLES
        ]
        tok = d.get("nextPageToken")
        if not tok:
            return out


def md5_b64(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return base64.b64encode(h.digest()).decode()


def fetch(cell: str, item: dict, raw: Path) -> None:
    dst = raw / item["name"].replace(".parquet.gz", ".parquet")
    if dst.exists() and dst.stat().st_size == int(item["size"]):
        return
    url = f"https://storage.googleapis.com/clusterdata_2019_{cell}/{item['name']}"
    part = dst.with_suffix(".part")
    for attempt in range(1, 6):
        r = subprocess.run(["curl", "-fsSL", "--retry", "5", "-o", str(part), url], check=False)
        if r.returncode == 0 and md5_b64(part) == item["md5Hash"]:
            part.rename(dst)
            return
        time.sleep(10 * attempt)
    raise RuntimeError(f"{item['name']}: download or MD5 check failed")


def download(cell: str, raw: Path, workers: int = 8) -> list[dict]:
    raw.mkdir(parents=True, exist_ok=True)
    items = listing(cell)
    gb = sum(int(i["size"]) for i in items) / 1e9
    log(f"cell {cell}: {len(items)} files, {gb:.1f} GB")
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for _ in pool.map(lambda it: fetch(cell, it, raw), items):
            done += 1
            if done % 200 == 0:
                log(f"cell {cell}: {done}/{len(items)} files")
    return items


# --------------------------------------------------------------------------- stage 1: placements

TIER5 = """CASE WHEN priority <= 99 THEN 1 WHEN priority <= 115 THEN 2 WHEN priority <= 119 THEN 3
                WHEN priority <= 359 THEN 4 ELSE 5 END"""


def _narrow(con: duckdb.DuckDBPyConnection, shards: str, tmp: Path) -> None:
    con.execute(
        f"""COPY (SELECT time, type, collection_id, instance_index, machine_id, priority,
                         scheduling_class, hash(collection_id, instance_index) % 16 AS b
                  FROM {shards} WHERE collection_type = 0 AND type BETWEEN 3 AND 8)
            TO '{tmp}' (FORMAT PARQUET, PARTITION_BY (b))"""
    )
    (tmp / "DONE").write_text("")


def placements(cell: str, raw: Path, out: Path) -> dict:
    """Aggregate placements per (window, machine, tier5, scheduling class)."""
    tmp = out / "_narrow"
    con = duckdb.connect()
    # 4 GB and 4 threads: this Mac has 17 GB, and other DuckDB jobs may run at the same time
    # (the first run, at 8 GB next to two other jobs, was swapped out and stalled)
    con.execute(f"SET temp_directory='{out / '_duckdb'}'; SET memory_limit='4GB'; SET threads=4")
    con.execute("SET preserve_insertion_order=false")
    shards = f"read_parquet('{raw}/instance_events-*.parquet')"
    stats = dict(
        zip(
            ["events", "task_events_3_to_8", "alloc_events"],
            con.execute(
                f"""SELECT count(*), count(*) FILTER (collection_type = 0 AND type BETWEEN 3 AND 8),
                           count(*) FILTER (collection_type = 1) FROM {shards}"""
            ).fetchone(),
            strict=True,
        )
    )
    # Narrow copy of task events, split into 16 buckets by task so each sort fits in memory.
    # Reused if a previous run finished it (marker file).
    if not (tmp / "DONE").exists():
        shutil.rmtree(tmp, ignore_errors=True)
        _narrow(con, shards, tmp)
    parts = []
    for b in range(16):
        src = f"read_parquet('{tmp}/b={b}/*.parquet')"
        overlaps = []
        for w, (d0, d1) in WINDOWS.items():
            ws, we = T0 + (d0 - 1) * DAY, T0 + d1 * DAY
            overlaps.append(
                f"""SELECT {w} AS window, machine_id, tier5, scheduling_class AS sc,
                           count(*) AS n,
                           sum(least(t_end, {we}) - greatest(t_start, {ws})) / {3600 * US} AS hours
                    FROM p WHERE t_start < {we} AND t_end > {ws} GROUP BY ALL"""
            )
        # At equal times, end events sort before SCHEDULE, so a placement ends before the next
        # one starts. Time 0 means "before the trace"; MAXINT or no end means "after".
        # The full tie-break makes next_t deterministic (rows equal in every ordered column
        # give the same result). Placements go to a temporary table, and each window is its
        # own query: as one statement (a CTE shared by a UNION ALL of the three windows, or the
        # UNION ALL over the table), DuckDB 1.5.6 stalled at 0% CPU (4 Oct); each part alone
        # takes seconds.
        con.execute(
            f"""CREATE OR REPLACE TEMP TABLE p AS
                WITH s AS (
                    SELECT time, type, machine_id, priority, scheduling_class,
                           lead(time) OVER (PARTITION BY collection_id, instance_index
                                            ORDER BY time, (type = 3), type, machine_id,
                                                     priority, scheduling_class) AS next_t
                    FROM {src})
                SELECT machine_id, {TIER5} AS tier5, scheduling_class,
                       greatest(time, {T0}) AS t_start,
                       least(CASE WHEN next_t IS NULL OR next_t = {MAXINT} THEN {T1}
                                  ELSE next_t END, {T1}) AS t_end
                FROM s WHERE type = 3 AND machine_id IS NOT NULL AND machine_id <> -1"""
        )
        parts += [con.execute(q).df() for q in overlaps]
        con.execute("DROP TABLE p")
        log(f"cell {cell}: bucket {b + 1}/16")
        ded = con.execute(
            f"SELECT count(*) FROM {src} WHERE type = 3 AND machine_id = -1"
        ).fetchone()
        stats["dedicated_schedules"] = stats.get("dedicated_schedules", 0) + ded[0]
    agg = pd.concat(parts).groupby(["window", "machine_id", "tier5", "sc"], as_index=False).sum()
    agg.insert(0, "cell", cell)
    agg.to_parquet(out / "placements.parquet", index=False)
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(out / "_duckdb", ignore_errors=True)
    stats["placement_rows"] = len(agg)
    stats["placements_by_window"] = agg.groupby("window")["n"].sum().astype(int).to_dict()
    return stats


def stage1(cell: str, keep_raw: bool, download_only: bool = False) -> None:
    out = GOOGLE / f"cell_{cell}"
    raw = out / "raw"
    t0 = time.time()
    if (out / "stage1.json").exists():
        log(f"cell {cell}: already aggregated")
        return
    items = download(cell, raw)
    if download_only:
        log(f"cell {cell}: downloaded in {time.time() - t0:.0f}s (download only)")
        return
    log(f"cell {cell}: downloaded in {time.time() - t0:.0f}s; aggregating")
    con = duckdb.connect()
    # same caps as placements(): an uncapped connection hung here once (4 Oct, cell a)
    con.execute(f"SET temp_directory='{out / '_duckdb'}'; SET memory_limit='4GB'; SET threads=4")
    for t in ("machine_events", "machine_attributes"):
        con.execute(
            f"COPY (SELECT * FROM read_parquet('{raw}/{t}-*.parquet')) TO '{out / t}.parquet' "
            "(FORMAT PARQUET)"
        )
    con.close()
    log(f"cell {cell}: machine tables copied")
    stats = placements(cell, raw, out)
    stats |= {
        "cell": cell,
        "files": len(items),
        "bytes": sum(int(i["size"]) for i in items),
        "md5": {i["name"]: i["md5Hash"] for i in items if not i["name"].startswith("instance")},
        "seconds": round(time.time() - t0),
        "finished": datetime.now().isoformat(timespec="seconds"),
    }
    (out / "stage1.json").write_text(json.dumps(stats, indent=2, default=int))
    if not keep_raw:
        for f in raw.glob("instance_events-*.parquet"):
            f.unlink()
    log(f"cell {cell}: done {stats['placements_by_window']}")


# --------------------------------------------------------------------------- stage 2: risk


def machine_risk(me: pd.DataFrame) -> pd.DataFrame:
    """Risk proxies per (window, machine), each using only events up to the window start."""
    me = me.sort_values(["machine_id", "time", "type"])
    rows = []
    for m, g in me.groupby("machine_id", sort=False):
        t, ty = g["time"].to_numpy(), g["type"].to_numpy()
        plat = g.loc[g["type"] == 1, "platform_id"]
        platform = plat.iloc[0] if len(plat) else g["platform_id"].dropna().iloc[0]
        adds = t[ty == 1]
        for w, (d0, _) in WINDOWS.items():
            ws = T0 + (d0 - 1) * DAY
            # up-time before ws: ADD starts, REMOVE ends an up interval
            up, start = 0, None
            removals = long_rem = 0
            for ti, typ in zip(t, ty, strict=True):
                if ti >= ws:
                    break
                ti = max(ti, T0)
                if typ == 1 and start is None:
                    start = ti
                elif typ == 2:
                    if start is not None:
                        up += ti - start
                        start = None
                    # a removal counts for window w only once its 24 h follow-up is before ws
                    if ti + LONG_REMOVAL <= ws:
                        removals += 1
                        nxt = adds[adds > ti]
                        if not len(nxt) or nxt[0] - ti > LONG_REMOVAL:
                            long_rem += 1
            if start is not None:
                up += ws - start
            rows.append((w, m, platform, up / DAY, removals, long_rem))
    return pd.DataFrame(
        rows, columns=["window", "machine_id", "platform", "up_days", "removals", "long_removals"]
    )


def add_proxies(r: pd.DataFrame) -> pd.DataFrame:
    out = []
    for _, g in r.groupby("window"):
        g = g.copy()
        p = g.groupby("platform")[["long_removals", "removals", "up_days"]].transform("sum")
        g["risk_platform"] = p["long_removals"] / p["up_days"].clip(lower=1e-9)
        g["risk_platform_all"] = p["removals"] / p["up_days"].clip(lower=1e-9)
        # gamma-Poisson shrinkage of each machine's long-removal rate towards its platform rate
        shrunk = np.empty(len(g))
        for _, idx in g.groupby("platform").indices.items():
            k = g["long_removals"].to_numpy()[idx]
            e = g["up_days"].to_numpy()[idx].clip(min=1e-9)
            mu = k.sum() / e.sum()
            raw = k / e
            tau2 = np.average((raw - mu) ** 2, weights=e) - mu / e.mean()
            beta = mu / tau2 if tau2 > 0 and mu > 0 else np.inf
            shrunk[idx] = mu if np.isinf(beta) else (k + mu * beta) / (e + beta)
        g["risk_machine"] = shrunk
        out.append(g)
    return pd.concat(out)


# --------------------------------------------------------------------------- stage 2: statistics


def mappings(tier5: np.ndarray, sc: np.ndarray) -> dict[str, np.ndarray]:
    """Tier score 0 (low), 1 (medium), 2 (high) under M1, M2, M3 (criticality_mapping.md)."""
    m1 = np.select([tier5 >= 4, tier5 == 3], [2, 1], 0)
    m2 = np.select([sc >= 2, sc == 1], [2, 1], 0)
    m3 = np.select([(tier5 >= 4) & (sc >= 2), (tier5 <= 2) & (sc <= 1)], [2, 0], 1)
    return {"M1": m1, "M2": m2, "M3": m3}


def tau_b(tab: np.ndarray) -> float:
    """Kendall tau-b from a contingency table (rows: ordered tier, columns: ordered risk)."""
    n = tab.sum()
    if n < 2:
        return np.nan
    # cumulative sums for "strictly below and right" (concordant) and "below and left"
    below = np.cumsum(tab[::-1], axis=0)[::-1]
    below = np.vstack([below[1:], np.zeros((1, tab.shape[1]))])  # rows strictly below
    right = np.cumsum(below[:, ::-1], axis=1)[:, ::-1]
    right = np.hstack([right[:, 1:], np.zeros((tab.shape[0], 1))])  # columns strictly right
    left = np.cumsum(below, axis=1)
    left = np.hstack([np.zeros((tab.shape[0], 1)), left[:, :-1]])  # columns strictly left
    p, q = (tab * right).sum(), (tab * left).sum()
    n0 = n * (n - 1) / 2
    r, c = tab.sum(1), tab.sum(0)
    n1, n2 = (r * (r - 1) / 2).sum(), (c * (c - 1) / 2).sum()
    den = np.sqrt((n0 - n1) * (n0 - n2))
    return (p - q) / den if den > 0 else np.nan


def spearman(tab: np.ndarray) -> float:
    """Tie-corrected (mid-rank) Spearman from a contingency table."""
    n = tab.sum()
    r, c = tab.sum(1), tab.sum(0)
    rr = np.cumsum(r) - r + (r + 1) / 2  # mid-ranks of the rows
    cr = np.cumsum(c) - c + (c + 1) / 2
    mr, mc = (r * rr).sum() / n, (c * cr).sum() / n
    cov = (tab * np.outer(rr - mr, cr - mc)).sum()
    vr, vc = (r * (rr - mr) ** 2).sum(), (c * (cr - mc) ** 2).sum()
    return cov / np.sqrt(vr * vc) if vr > 0 and vc > 0 else np.nan


def gini(x: np.ndarray, w: np.ndarray) -> float:
    o = np.argsort(x)
    x, w = x[o], w[o]
    cw = np.cumsum(w) / w.sum()
    cx = np.cumsum(x * w) / (x * w).sum()
    return 1 - np.sum((cx[1:] + cx[:-1]) * np.diff(cw)) - cx[0] * cw[0]


class CellData:
    """Per (window): machine-level tier counts and the machine's risk index (for bootstraps)."""

    def __init__(self, pl: pd.DataFrame, risk: pd.DataFrame, mapping: str, proxy: str, weight: str):
        self.windows = {}
        for w, g in pl.groupby("window"):
            g = g.assign(score=mappings(g["tier5"].to_numpy(), g["sc"].to_numpy())[mapping])
            cnt = g.pivot_table(index="machine_id", columns="score", values=weight, aggfunc="sum")
            cnt = cnt.reindex(columns=[0, 1, 2]).fillna(0)
            rk = risk[risk["window"] == w].set_index("machine_id")[proxy]
            cnt = cnt.join(rk, how="inner")
            levels, idx = np.unique(cnt[proxy].to_numpy(), return_inverse=True)
            self.windows[w] = (
                cnt[[0, 1, 2]].to_numpy(float),
                idx,
                len(levels),
                cnt.index.to_numpy(),
            )

    def machines(self) -> np.ndarray:
        return np.unique(np.concatenate([v[3] for v in self.windows.values()]))

    def stat(self, fn, mult: dict | None = None) -> float:
        vals = []
        for _w, (cnt, idx, k, _mids) in self.windows.items():
            c = cnt if mult is None else cnt * mult[_w][:, None]
            tab = np.vstack([np.bincount(idx, weights=c[:, j], minlength=k) for j in range(3)])
            vals.append(fn(tab))
        return float(np.nanmean(vals))


def bootstrap(cd: CellData, fn, rng: np.random.Generator) -> tuple[float, float, float, str]:
    est = cd.stat(fn)
    ms = cd.machines()
    pos = {w: np.searchsorted(ms, v[3]) for w, v in cd.windows.items()}
    reps = np.empty(N_BOOT)
    for b in range(N_BOOT):
        mult = np.bincount(rng.integers(0, len(ms), len(ms)), minlength=len(ms)).astype(float)
        reps[b] = cd.stat(fn, {w: mult[p] for w, p in pos.items()})
    # BCa: bias from the bootstrap, acceleration from a grouped jackknife (100 machine groups)
    z0 = _ppf((reps < est).mean() + 0.5 * (reps == est).mean())
    grp = rng.integers(0, 100, len(ms))
    jack = np.array(
        [cd.stat(fn, {w: (grp[p] != j).astype(float) for w, p in pos.items()}) for j in range(100)]
    )
    d = jack.mean() - jack
    a = (d**3).sum() / (6 * ((d**2).sum()) ** 1.5) if (d**2).sum() > 0 else 0.0
    if not np.isfinite(z0) or abs(a) > 0.25:
        lo, hi = np.nanpercentile(reps, [2.5, 97.5])
        return est, lo, hi, "percentile"
    qs = []
    for z in (_ppf(0.025), _ppf(0.975)):
        qs.append(_cdf(z0 + (z0 + z) / (1 - a * (z0 + z))))
    lo, hi = np.nanpercentile(reps, [100 * qs[0], 100 * qs[1]])
    return est, lo, hi, "BCa"


def _ppf(p: float) -> float:
    from scipy.stats import norm

    return float(norm.ppf(np.clip(p, 1e-12, 1 - 1e-12)))


def _cdf(z: float) -> float:
    from scipy.stats import norm

    return float(norm.cdf(z))


# --------------------------------------------------------------------------- mapping to rho_L


def copula_table(rho: float, p_row: np.ndarray, p_col: np.ndarray) -> np.ndarray:
    """Cell probabilities of a Gaussian copula with given margins (rows and columns ordered)."""
    from scipy.stats import multivariate_normal, norm

    a = norm.ppf(np.clip(np.cumsum(p_row)[:-1], 1e-12, 1 - 1e-12))
    b = norm.ppf(np.clip(np.cumsum(p_col)[:-1], 1e-12, 1 - 1e-12))
    a = np.concatenate([[-np.inf], a, [np.inf]])
    b = np.concatenate([[-np.inf], b, [np.inf]])
    mvn = multivariate_normal(mean=[0, 0], cov=[[1, rho], [rho, 1]])

    def F(x, y):
        if x == -np.inf or y == -np.inf:
            return 0.0
        if x == np.inf and y == np.inf:
            return 1.0
        if x == np.inf:
            return float(norm.cdf(y))
        if y == np.inf:
            return float(norm.cdf(x))
        return float(mvn.cdf([x, y]))

    G = np.array([[F(x, y) for y in b] for x in a])
    return np.clip(G[1:, 1:] - G[:-1, 1:] - G[1:, :-1] + G[:-1, :-1], 0, None)


LATENT_GRID = np.linspace(-0.95, 0.95, 39)


def curve(fn, p_row, p_col, grid=LATENT_GRID) -> tuple[np.ndarray, np.ndarray]:
    vals = np.array([fn(copula_table(r, p_row, p_col) * 1e6) for r in grid])
    return grid, vals


def invert(grid, vals, x) -> float:
    if not np.isfinite(x):
        return np.nan
    if x <= vals.min():
        return float(grid[0])
    if x >= vals.max():
        return float(grid[-1])
    return float(np.interp(x, vals, grid))


def v1_margins(n_levels: int = 40) -> tuple[np.ndarray, np.ndarray]:
    """v1's margins: Azure tier shares over VMs, and v1's host-risk score over VM slots."""
    vm = pd.read_csv(
        ROOT / "data" / "processed" / "azure_vms_clean.csv.gz", usecols=["criticality_weight"]
    )
    p_row = vm["criticality_weight"].value_counts(normalize=True).sort_index().to_numpy()
    ttf = pd.read_csv(ROOT / "data" / "processed" / "ttf_lookup_table.csv")
    drv = pd.read_csv(ROOT / "data" / "processed" / "backblaze_drives_clean.csv").dropna(
        subset=["age_days"]
    )
    top = set(ttf.loc[ttf["model_grp"] != "OTHER", "model_grp"])
    grp = np.where(drv["model"].isin(top), drv["model"], "OTHER")
    risk = pd.Series(grp).map(ttf.groupby("model_grp")["p_fail_within_window"].mean())
    p_col = risk.value_counts(normalize=True).sort_index().to_numpy()
    return p_row, p_col


def classify(lo: float, hi: float, ph: float, c0: float) -> str:
    """PROTOCOL.md section 7: A above, B straddle or too wide, C1 below, C0 below c0."""
    if hi - lo > 0.30:
        return "B"
    if lo > ph:
        return "A"
    if hi < ph:
        return "C1" if hi >= c0 else "C0"
    return "B"


# --------------------------------------------------------------------------- stage 2: main


def analyse() -> None:
    rng = np.random.default_rng(SEED)
    RES.mkdir(parents=True, exist_ok=True)
    rows, extra = [], {}
    # pH on the latent axis: the rho_L that gives v1's crossover (tie-corrected Spearman 0.30)
    # under v1's own margins
    v1r, v1c = v1_margins()
    g_v1, s_v1 = curve(spearman, v1r, v1c)
    ph_latent = invert(g_v1, s_v1, P_H)
    c0_latent = invert(g_v1, s_v1, P_C0)
    extra |= {"pH_latent": ph_latent, "c0_latent": c0_latent}
    log(f"pH = {P_H} (v1 Spearman) -> rho_L = {ph_latent:.3f}")
    for cell in CELLS:
        out = GOOGLE / f"cell_{cell}"
        if not (out / "placements.parquet").exists():
            log(f"cell {cell}: not aggregated yet, skipped")
            continue
        pl = pd.read_parquet(out / "placements.parquet")
        risk = add_proxies(machine_risk(pd.read_parquet(out / "machine_events.parquet")))
        risk.to_parquet(out / "risk.parquet", index=False)
        ex = {}
        for mapping in ("M1", "M2", "M3"):
            for proxy in ("risk_platform", "risk_machine", "risk_platform_all"):
                for weight in ("n", "hours"):
                    if weight == "hours" and (mapping != "M1" or proxy != "risk_platform"):
                        continue
                    cd = CellData(pl, risk, mapping, proxy, weight)
                    for name, fn in (("tau_b", tau_b), ("spearman", spearman)):
                        est, lo, hi, kind = bootstrap(cd, fn, rng)
                        # margins of this cell (placement-weighted), for the latent mapping
                        tabs = [
                            np.vstack(
                                [np.bincount(i, weights=c[:, j], minlength=k) for j in range(3)]
                            )
                            for c, i, k, _ in cd.windows.values()
                        ]
                        tab = sum(t / t.sum() for t in tabs)
                        p_row, p_col = tab.sum(1) / tab.sum(), tab.sum(0) / tab.sum()
                        if len(p_col) > 60:  # bin many risk levels for the copula curve
                            edges = np.linspace(0, 1, 41)
                            cum = np.cumsum(p_col)
                            p_col = np.diff(np.interp(edges, np.r_[0, cum], np.r_[0, cum]))
                            p_col = p_col[p_col > 0]
                        g, v = curve(fn, p_row, p_col)
                        lat = [invert(g, v, x) for x in (est, lo, hi)]
                        rows.append(
                            dict(
                                cell=cell,
                                mapping=mapping,
                                proxy=proxy,
                                weight=weight,
                                stat=name,
                                estimate=est,
                                ci_low=lo,
                                ci_high=hi,
                                ci=kind,
                                latent=lat[0],
                                latent_low=lat[1],
                                latent_high=lat[2],
                                windows=len(cd.windows),
                                machines=len(cd.machines()),
                                risk_levels=int(np.mean([v[2] for v in cd.windows.values()])),
                                share_high=float(p_row[2]),
                                share_medium=float(p_row[1]),
                            )
                        )
                    log(f"cell {cell} {mapping} {proxy} {weight}: done")
        # dispersion: Gini of the high-tier share across machines (M1), per window
        m1 = pl.assign(score=mappings(pl["tier5"].to_numpy(), pl["sc"].to_numpy())["M1"])
        gin = {}
        for w, g in m1.groupby("window"):
            per = g.groupby("machine_id").apply(
                lambda x: pd.Series({"hi": x.loc[x["score"] == 2, "n"].sum(), "all": x["n"].sum()}),
                include_groups=False,
            )
            gin[int(w)] = gini((per["hi"] / per["all"]).to_numpy(), per["all"].to_numpy(float))
        ex["gini_high_share"] = gin
        ex["stage1"] = json.loads((out / "stage1.json").read_text())
        ex["platform_long_removal_rate_per_machine_day"] = (
            risk[risk["window"] == 2]
            .groupby("platform")["risk_platform"]
            .first()
            .round(5)
            .to_dict()
        )
        extra[cell] = ex
    tab = pd.DataFrame(rows)
    # G1 class per cell: M1, platform proxy, placement weights, tau-b on the latent axis
    prim = tab.query("mapping == 'M1' and proxy == 'risk_platform' and weight == 'n'")
    g1 = {}
    for _, r in prim[prim["stat"] == "tau_b"].iterrows():
        g1[r["cell"]] = classify(r["latent_low"], r["latent_high"], ph_latent, c0_latent)
    for _, r in prim[prim["stat"] == "spearman"].iterrows():
        extra.setdefault("direct_spearman_class", {})[r["cell"]] = classify(
            r["ci_low"], r["ci_high"], P_H, P_C0
        )
    counts = pd.Series(list(g1.values())).value_counts()
    majority = counts.index[0] if len(counts) and counts.iloc[0] > len(g1) / 2 else "B"
    extra |= {"g1_class_per_cell": g1, "g1_majority": majority if g1 else None}
    tab.to_csv(RES / "trace_rho_table.csv", index=False)
    (RES / "trace_rho.json").write_text(json.dumps(extra, indent=2, default=str))
    figure(tab, ph_latent)
    print(prim.round(3).to_string())
    print(
        json.dumps(
            {k: extra[k] for k in ("pH_latent", "g1_class_per_cell", "g1_majority")}, indent=1
        )
    )


def figure(tab: pd.DataFrame, ph_latent: float) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = tab.query("stat == 'tau_b' and weight == 'n'")
    fig, ax = plt.subplots(figsize=(7, 3.6))
    labels = []
    for i, (_, r) in enumerate(t.iterrows()):
        ax.errorbar(
            r["latent"],
            i,
            xerr=[[r["latent"] - r["latent_low"]], [r["latent_high"] - r["latent"]]],
            fmt="o",
            color="C0" if r["mapping"] == "M1" and r["proxy"] == "risk_platform" else "0.6",
        )
        labels.append(f"{r['cell']} {r['mapping']} {r['proxy'].replace('risk_', '')}")
    ax.axvline(ph_latent, color="C3", ls="--", label=f"break-even (latent {ph_latent:.2f})")
    ax.axvline(0, color="0.3", lw=0.8)
    ax.set_yticks(range(len(labels)), labels, fontsize=6)
    ax.set_xlabel("latent rho_L (95% CI); removal proxy, not hardware failure")
    ax.legend(fontsize=7)
    fig.tight_layout()
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / "v2_trace_rho.pdf")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--cell", choices=CELLS)
    g.add_argument("--analyse", action="store_true")
    ap.add_argument("--keep-raw", action="store_true")
    ap.add_argument("--download-only", action="store_true")
    args = ap.parse_args()
    if args.cell:
        stage1(args.cell, args.keep_raw, args.download_only)
    else:
        analyse()


if __name__ == "__main__":
    main()
