"""Week 7: temporal hazard model v2 against the v1 model, with calibration and bootstrap CIs.

Input: data/v2/features/*.parquet from 11_features.py (sampled drive-days with weights w).

Splits (by calendar time, never by row; label_spec.md "Splits"):
  train = first 70% of days, validation = next 15%, test = last 15%.
  A point near the end of its split whose label is not decided inside that split is dropped.
  Drives that fail in the test period are excluded from training.
  Rolling origin: three 3-month test folds before the main test period, each trained on all
  earlier data (HistGBM, H = 30, ranking metrics only).

Models (sample weights = inverse sampling probabilities only; no class weights):
  v2     HistGradientBoosting on all features (model as a categorical, top 30 + OTHER)
  logit  logistic regression on the same features (sanity check)
  v1     HistGradientBoosting on v1's features only: model group (top 15 + OTHER),
         capacity, age; v1's own model was trained with a random split, so it is refitted here
         on the same temporal training data and only the feature set differs
Isotonic calibration on the validation period; metrics on the test period: ROC-AUC, PR-AUC,
Brier, ECE (20 equal-weight bins), precision in the top 1% and 5%; 95% CIs from 1,000 Poisson
bootstrap replicates over drives.

Writes results/v2/model_v2_metrics.csv, results/v2/model_v2.json, docs/v2/failure_model_v2.md
(tables; the text around them is written by hand), results/figures/v2_reliability.pdf, and the
fitted models in data/v2/models/ (not committed).

Run from the repository root:  .venv/bin/python scripts/v2/12_train.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import duckdb
import joblib
import matplotlib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FEAT = ROOT / "data" / "v2" / "features"
MODELS = ROOT / "data" / "v2" / "models"
RES, FIG, DOCS = ROOT / "results" / "v2", ROOT / "results" / "figures", ROOT / "docs" / "v2"
SEED = 20261004
N_BOOT = 1_000
HORIZONS = (30, 14, 7)  # 30 is primary
NUMERIC = [
    *(f"s{i}{suf}" for i in (5, 187, 188, 197, 198) for suf in ("", "_d7", "_d30", "_max30")),
    "age_days",
    "temp",
    "temp_max30",
    "days_since_nz5",
    "days_since_nz197",
    "capacity_tb",
    *(f"s{i}_missing" for i in (5, 187, 188, 197, 198, 9, 194)),
]


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


# --------------------------------------------------------------------------- data


def load(years: int | None = 3) -> pd.DataFrame:
    """Feature rows of the last `years` years (Week 7's period; None = every file). Pinned
    because older quarters were added later for the Week 16 drift study, and they must not
    change Week 7's split."""
    df = duckdb.sql(f"SELECT * FROM read_parquet('{FEAT}/*.parquet')").df()
    df["date"] = pd.to_datetime(df["date"])
    df["fail_date"] = pd.to_datetime(df["fail_date"])
    if years is not None:
        last = df["date"].max()
        df = df[df["date"] > last - pd.DateOffset(years=years)].reset_index(drop=True)
    return df


def split_dates(df: pd.DataFrame) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    days = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    a, b = days[int(0.70 * len(days))], days[int(0.85 * len(days))]
    one = pd.Timedelta(days=1)
    return {"train": (days[0], a - one), "val": (a, b - one), "test": (b, days[-1])}


def part(df: pd.DataFrame, lo, hi, h: int, drop_drives=None) -> pd.DataFrame:
    """Rows of [lo, hi] whose H-day label is decided inside the period (label_spec.md)."""
    s = df[(df["date"] >= lo) & (df["date"] <= hi) & (df[f"ok{h}"] == 1)]
    decided = (s["date"] <= hi - pd.Timedelta(days=h)) | (
        s["fail_date"].notna() & (s["fail_date"] <= hi)
    )
    s = s[decided]
    if drop_drives is not None:
        s = s[~s["serial_number"].isin(drop_drives)]
    return s


def categories(train: pd.DataFrame, n: int) -> list[str]:
    days = train.groupby("model_key")["w"].sum().sort_values(ascending=False)
    return list(days.index[:n])


def design(s: pd.DataFrame, cats: list[str], kind: str) -> pd.DataFrame:
    m = s["model_key"].where(s["model_key"].isin(cats), "OTHER")
    if kind == "v1":
        x = pd.DataFrame(
            {"model_grp": m, "capacity_tb": s["capacity_tb"], "age_days": s["age_days"]}
        )
    else:
        x = s[NUMERIC].astype(float).copy()
        x["model_grp"] = m
    x["model_grp"] = pd.Categorical(x["model_grp"], categories=[*cats, "OTHER"])
    return x


def fit(kind: str, x: pd.DataFrame, y: np.ndarray, w: np.ndarray):
    if kind == "logit":
        xx = pd.get_dummies(x, columns=["model_grp"], dtype=float).fillna(0.0)
        est = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
        est.fit(xx, y, logisticregression__sample_weight=w)
        return est, list(xx.columns)
    est = HistGradientBoostingClassifier(
        categorical_features="from_dtype",
        max_iter=400,
        learning_rate=0.05,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=SEED,
    )
    est.fit(x, y, sample_weight=w)
    return est, None


def predict(est, cols, x: pd.DataFrame) -> np.ndarray:
    if cols is not None:
        x = pd.get_dummies(x, columns=["model_grp"], dtype=float).reindex(columns=cols).fillna(0.0)
    return est.predict_proba(x)[:, 1]


# --------------------------------------------------------------------------- metrics


class Scored:
    """Rows grouped by distinct score (descending) so that weighted metrics, ties included,
    are a few bincounts: fast enough for 1,000 bootstrap replicates."""

    def __init__(self, y: np.ndarray, p: np.ndarray, bins: int = 20):
        self.y, self.p = y.astype(float), p
        uniq, inv = np.unique(-p, return_inverse=True)
        self.g, self.score, self.k = inv, -uniq, len(uniq)
        o = np.argsort(p, kind="stable")  # equal-count bins of rows for ECE (fixed per test set)
        self.bin = np.empty(len(p), dtype=int)
        self.bin[o] = np.minimum(np.arange(len(p)) * bins // len(p), bins - 1)
        self.nb = bins

    def metrics(self, w: np.ndarray) -> dict:
        y, k = self.y, self.k
        w1 = np.bincount(self.g, w * y, k)
        w0 = np.bincount(self.g, w * (1 - y), k)
        W1, W0 = w1.sum(), w0.sum()
        c1, c0 = np.cumsum(w1), np.cumsum(w0)
        below0 = W0 - c0  # negative weight with a strictly lower score
        auc = (w1 * (below0 + 0.5 * w0)).sum() / (W1 * W0)
        prec = c1 / np.maximum(c1 + c0, 1e-300)
        ap = (np.diff(np.r_[0.0, c1]) / W1 * prec).sum()
        b1 = np.bincount(self.bin, w * y, self.nb)
        bp = np.bincount(self.bin, w * self.p, self.nb)
        out = {
            "roc_auc": auc,
            "pr_auc": ap,
            "brier": float((w * (self.p - y) ** 2).sum() / w.sum()),
            "ece": float(np.abs(b1 - bp).sum() / w.sum()),
            "base_rate": float(W1 / (W1 + W0)),
        }
        cw = c1 + c0
        for name, frac in (("prec_top1", 0.01), ("prec_top5", 0.05)):
            t = frac * cw[-1]
            i = int(np.searchsorted(cw, t))  # tie group that crosses the cut, taken pro rata
            prev1, prev = (c1[i - 1], cw[i - 1]) if i else (0.0, 0.0)
            f = (t - prev) / (w1[i] + w0[i])
            out[name] = float((prev1 + f * w1[i]) / t)
        return out


def metrics(y, p, w) -> dict:
    return Scored(y, p).metrics(w)


def boot_ci(y, preds: dict, w, drives, rng) -> dict:
    """Poisson bootstrap over drives: every row of a drive gets that drive's weight."""
    codes, uniq = pd.factorize(drives)
    scored = {k: Scored(y, p) for k, p in preds.items()}
    reps = {k: [] for k in preds}
    for _ in range(N_BOOT):
        bw = w * rng.poisson(1.0, len(uniq))[codes]
        for k, sc in scored.items():
            reps[k].append(sc.metrics(bw))
    out = {}
    for k, rs in reps.items():
        r = pd.DataFrame(rs)
        out[k] = {c: (float(r[c].quantile(0.025)), float(r[c].quantile(0.975))) for c in r}
        if k != "v1" and "v1" in reps:  # paired difference against v1, same replicates
            d = r["pr_auc"] - pd.DataFrame(reps["v1"])["pr_auc"]
            out[k]["pr_auc_minus_v1"] = (float(d.quantile(0.025)), float(d.quantile(0.975)))
    return out


def check_metrics(rng) -> None:
    """The fast metrics agree with scikit-learn (ties and weights included)."""
    y = rng.random(5000) < 0.05
    p = np.round(rng.random(5000) * (0.5 + y), 2)  # rounded: many ties
    w = rng.choice([1.0, 50.0], 5000)
    m = metrics(y, p, w)
    assert abs(m["roc_auc"] - roc_auc_score(y, p, sample_weight=w)) < 1e-9
    assert abs(m["pr_auc"] - average_precision_score(y, p, sample_weight=w)) < 1e-9


# --------------------------------------------------------------------------- main


def main() -> None:
    rng = np.random.default_rng(SEED)
    check_metrics(rng)
    for d in (MODELS, RES, FIG):
        d.mkdir(parents=True, exist_ok=True)
    df = load()
    sp = split_dates(df)
    log(
        f"{len(df):,} rows; splits "
        + ", ".join(f"{k} {a.date()}..{b.date()}" for k, (a, b) in sp.items())
    )
    test_fail = set(
        df.loc[df["fail_date"].between(*sp["test"]), "serial_number"].unique()
    )  # drives that fail in the test period: never in training
    rows, report, rel = (
        [],
        {"splits": {k: [str(a.date()), str(b.date())] for k, (a, b) in sp.items()}},
        {},
    )
    audit = {}
    for h in HORIZONS:
        tr = part(df, *sp["train"], h, drop_drives=test_fail)
        va = part(df, *sp["val"], h)
        te = part(df, *sp["test"], h)
        cats_v2, cats_v1 = categories(tr, 30), categories(tr, 15)
        y_tr, y_va, y_te = (s[f"y{h}"].to_numpy() for s in (tr, va, te))
        kinds = ("v2", "logit", "v1") if h == 30 else ("v2", "v1")
        preds = {}
        for kind in kinds:
            cats = cats_v1 if kind == "v1" else cats_v2
            xk = "v1" if kind == "v1" else "v2"
            t = time.time()
            est, cols = fit(kind, design(tr, cats, xk), y_tr, tr["w"].to_numpy())
            p_va = predict(est, cols, design(va, cats, xk))
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
            iso.fit(p_va, y_va, sample_weight=va["w"].to_numpy())
            p_te_raw = predict(est, cols, design(te, cats, xk))
            p_te = iso.predict(p_te_raw)
            preds[kind] = p_te
            joblib.dump(
                {"model": est, "cols": cols, "iso": iso, "cats": cats},
                MODELS / f"{kind}_h{h}.joblib",
            )
            for cal, p in (("raw", p_te_raw), ("isotonic", p_te)):
                rows.append(
                    {
                        "h": h,
                        "model": kind,
                        "calibration": cal,
                        **metrics(y_te, p, te["w"].to_numpy()),
                    }
                )
            log(
                f"H={h} {kind}: fitted in {time.time() - t:.0f}s, "
                f"test PR-AUC {rows[-1]['pr_auc']:.4f}"
            )
            if h == 30:
                rel[kind] = (y_te, p_te, te["w"].to_numpy())
        ci = boot_ci(y_te, preds, te["w"].to_numpy(), te["serial_number"].to_numpy(), rng)
        for r in rows:
            if r["h"] == h and r["calibration"] == "isotonic":
                for k, (lo, hi) in ci[r["model"]].items():
                    r[f"{k}_lo"], r[f"{k}_hi"] = lo, hi
        report[f"h{h}"] = {
            "n_train": len(tr),
            "n_val": len(va),
            "n_test": len(te),
            "train_positives": int(y_tr.sum()),
            "test_positives": int(y_te.sum()),
            "test_drives": int(te["serial_number"].nunique()),
        }
        audit[f"h{h}"] = {
            "train_drives_failing_in_test": int(tr["serial_number"].isin(test_fail).sum()),
            "train_labels_past_train_end": int(
                (
                    (tr["date"] + pd.Timedelta(days=h) > sp["train"][1])
                    & ~(tr["fail_date"] <= sp["train"][1])
                ).sum()
            ),
        }
    # rolling origin (H = 30, HistGBM, ranking metrics): three 3-month folds before the test period
    roll = []
    t_end = sp["test"][0] - pd.Timedelta(days=1)
    for k in (3, 2, 1):
        lo = t_end - pd.DateOffset(months=3 * k) + pd.Timedelta(days=1)
        hi = lo + pd.DateOffset(months=3) - pd.Timedelta(days=1)
        tr = part(df, df["date"].min(), lo - pd.Timedelta(days=1), 30)
        fe = part(df, lo, hi, 30)
        tr = tr[~tr["serial_number"].isin(fe.loc[fe["fail_date"].notna(), "serial_number"])]
        cats = categories(tr, 30)
        est, _ = fit("v2", design(tr, cats, "v2"), tr["y30"].to_numpy(), tr["w"].to_numpy())
        p = predict(est, None, design(fe, cats, "v2"))
        m = metrics(fe["y30"].to_numpy(), p, fe["w"].to_numpy())
        roll.append(
            {
                "fold_test": f"{lo.date()}..{hi.date()}",
                "roc_auc": m["roc_auc"],
                "pr_auc": m["pr_auc"],
            }
        )
        log(f"rolling fold {lo.date()}: PR-AUC {m['pr_auc']:.4f}")
    report["rolling_origin"] = roll
    report["leakage_audit"] = audit | {
        "windows": "all feature windows are RANGE ... PRECEDING AND CURRENT ROW (11_features.py)",
        "first_nonzero_dates": "used only when on or before the prediction day",
    }
    tab = pd.DataFrame(rows)
    tab.to_csv(RES / "model_v2_metrics.csv", index=False)
    (RES / "model_v2.json").write_text(json.dumps(report, indent=2, default=str))
    reliability(rel)
    write_doc(tab, report)
    print(tab.query("calibration == 'isotonic'").round(4).to_string())


def reliability(rel: dict) -> None:
    fig, ax = plt.subplots(figsize=(4.5, 4.2))
    for kind, (y, p, w) in rel.items():
        o = np.argsort(p)
        edges = np.searchsorted(np.cumsum(w[o]) / w.sum(), np.linspace(0, 1, 21)[1:-1])
        xs, ys = [], []
        for idx in np.split(o, edges):
            if len(idx):
                xs.append(np.average(p[idx], weights=w[idx]))
                ys.append(np.average(y[idx], weights=w[idx]))
        ax.plot(xs, ys, marker="o", ms=3, label=kind)
    lim = max(ax.get_xlim()[1], ax.get_ylim()[1])
    ax.plot([0, lim], [0, lim], color="0.5", lw=0.8)
    ax.set(xscale="symlog", yscale="symlog", xlabel="predicted p (30 days)", ylabel="observed rate")
    ax.set_title("Reliability, test period (isotonic)", fontsize=9)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG / "v2_reliability.pdf")
    plt.close(fig)


def write_doc(tab: pd.DataFrame, report: dict) -> None:
    t = tab.query("calibration == 'isotonic'").copy()

    def ci(r, k, f="{:.4f}"):
        lo, hi = r.get(f"{k}_lo"), r.get(f"{k}_hi")
        v = f.format(r[k])
        return v if lo is None or pd.isna(lo) else f"{v} [{f.format(lo)}, {f.format(hi)}]"

    lines = [
        "| H | model | ROC-AUC | PR-AUC | Brier | ECE | precision, top 1% | precision, top 5% |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, r in t.iterrows():
        lines.append(
            f"| {r['h']} | {r['model']} | {ci(r, 'roc_auc')} | {ci(r, 'pr_auc')} "
            f"| {ci(r, 'brier', '{:.2e}')} "
            f"| {ci(r, 'ece', '{:.2e}')} | {ci(r, 'prec_top1')} | {ci(r, 'prec_top5')} |"
        )
    gen = "\n".join(lines)
    doc = DOCS / "failure_model_v2.md"
    marker = "<!-- generated: metrics table -->"
    body = doc.read_text() if doc.exists() else f"# Failure model v2\n\n{marker}\n{marker}\n"
    a, _, rest = body.partition(marker)
    _, _, c = rest.partition(marker)
    doc.write_text(f"{a}{marker}\n{gen}\n\nSplits: {report['splits']}\n{marker}{c}")


if __name__ == "__main__":
    main()
