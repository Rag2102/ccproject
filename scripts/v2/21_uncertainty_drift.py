"""Week 16, tasks 1-2: uncertainty on p (bootstrap ensemble) and the drift study.

--ensemble  On Week 7's split (H = 30, v2 features): 20 gradient-boosting models, each fitted
            on a Poisson bootstrap of training drives (cluster bootstrap) and calibrated
            isotonically on the validation period. On the test period: the ensemble mean and
            the 5-95% interval of p per drive-day. Reports PR-AUC and ECE of the mean against
            the single Week 7 model, the relative interval width by decile of p, and how often
            the interval straddles the cost-tuned threshold (where a decision is uncertain).
--drift     Train on 2019..Y (Y = 2020-2024), calibrate on Y's last quarter, test on Y+1 and Y+2.
            ECE, reliability slope (logistic regression of the outcome on logit p) and PR-AUC,
            without and with rolling recalibration (isotonic refitted on the last quarter
            before each test year).
--policy    Policy-cost effect of drift: the measured slopes mapped to the simulator's
            miscalibration (p' = p^gamma has slope about 1 / gamma, so gamma = 1 / slope),
            BAM's cost at that gamma against gamma = 1, regime A3, dev seeds 101-105. This is a
            bridge until the simulator scores replayed drives with the model itself.

Writes results/v2/uncertainty_w16.json, drift_w16.json, drift_policy_w16.json.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("tr", ROOT / "scripts/v2/12_train.py")
tr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tr)

RES = ROOT / "results" / "v2"
H = 30
N_MODELS = 20


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def slope(y, p, w) -> float:
    from sklearn.linear_model import LogisticRegression

    x = np.log(np.clip(p, 1e-9, 1 - 1e-9) / np.clip(1 - p, 1e-9, 1))[:, None]
    return float(LogisticRegression(C=1e6, max_iter=1000).fit(x, y, sample_weight=w).coef_[0, 0])


def scores(y, p, w) -> dict:
    m = tr.metrics(y, p, w)
    return {
        "pr_auc": float(m["pr_auc"]),
        "roc_auc": float(m["roc_auc"]),
        "ece": float(m["ece"]),
        "slope": slope(y, p, w),
        "mean_p": float(np.average(p, weights=w)),
        "base_rate": float(m["base_rate"]),
    }


# --------------------------------------------------------------------------- ensemble
def ensemble() -> None:
    df = tr.load()
    sp = tr.split_dates(df)
    test_fail = set(df.loc[df["fail_date"].between(*sp["test"]), "serial_number"].unique())
    trn = tr.part(df, *sp["train"], H, drop_drives=test_fail)
    val = tr.part(df, *sp["val"], H)
    tst = tr.part(df, *sp["test"], H)
    cats = tr.categories(trn, 30)
    x_tr, x_va, x_te = (tr.design(s, cats, "v2") for s in (trn, val, tst))
    y_tr, y_va, y_te = (s[f"y{H}"].to_numpy() for s in (trn, val, tst))
    w_tr, w_va, w_te = (s["w"].to_numpy() for s in (trn, val, tst))
    codes, uniq = pd.factorize(trn["serial_number"])
    rng = np.random.default_rng(16)
    preds = []
    for k in range(N_MODELS):
        t = time.time()
        bw = w_tr * rng.poisson(1.0, len(uniq))[codes]
        keep = bw > 0
        est, cols = tr.fit("v2", x_tr[keep], y_tr[keep], bw[keep])
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
        iso.fit(tr.predict(est, cols, x_va), y_va, sample_weight=w_va)
        preds.append(iso.predict(tr.predict(est, cols, x_te)))
        log(f"ensemble member {k + 1}/{N_MODELS}: {time.time() - t:.0f}s")
    P = np.vstack(preds)
    mean, lo, hi = P.mean(0), np.quantile(P, 0.05, 0), np.quantile(P, 0.95, 0)
    import joblib

    single = joblib.load(tr.MODELS / "v2_h30.joblib")
    p1 = single["iso"].predict(tr.predict(single["model"], single["cols"], x_te))
    rel = (hi - lo) / np.maximum(mean, 1e-9)
    dec = pd.qcut(mean, 10, labels=False, duplicates="drop")
    tau = json.loads((RES / "pilot_w14.json").read_text())["p2"]["A3@0.02"]["cost"]["tau"]
    out = {
        "members": N_MODELS,
        "test_rows": int(len(y_te)),
        "single_model": scores(y_te, p1, w_te),
        "ensemble_mean": scores(y_te, mean, w_te),
        "rel_width_median": float(np.median(rel)),
        "rel_width_by_decile_of_p": {
            int(d): float(np.median(rel[dec == d])) for d in np.unique(dec)
        },
        "single_outside_interval_share": float(np.mean((p1 < lo) | (p1 > hi))),
        "drive_day_tau_cost_tuned": tau,
        "note": "tau is a 30-day host threshold from the simulator; drive-level p is smaller, "
        "so the straddle share is reported at tau / 4 (four drives per host) too",
        "straddle_tau_share": float(np.mean((lo < tau) & (hi > tau))),
        "straddle_tau_over_4_share": float(np.mean((lo < tau / 4) & (hi > tau / 4))),
    }
    (RES / "uncertainty_w16.json").write_text(json.dumps(out, indent=2))
    pd.DataFrame(
        {
            "serial_number": tst["serial_number"].to_numpy(),
            "date": tst["date"].to_numpy(),
            "p_mean": mean,
            "p_lo": lo,
            "p_hi": hi,
        }
    ).to_parquet(ROOT / "data" / "v2" / "ensemble_test_h30.parquet", index=False)
    log(json.dumps({k: out[k] for k in ("single_model", "ensemble_mean", "rel_width_median")}))


# --------------------------------------------------------------------------- drift
def drift() -> None:
    df = tr.load(years=None)
    df = df[df["date"] >= "2019-01-01"].reset_index(drop=True)
    log(f"{len(df):,} rows, {df['date'].min().date()}..{df['date'].max().date()}")
    res = []
    for Y in range(2020, 2025):
        t = time.time()
        start = pd.Timestamp("2019-01-01")
        end_y = pd.Timestamp(f"{Y}-12-31")
        cal_lo = pd.Timestamp(f"{Y}-10-01")
        test_years = [Y + 1, Y + 2]
        test_fail = set(
            df.loc[df["fail_date"] > end_y, "serial_number"].unique()
        )  # drives failing after training: never in training (same rule as Week 7)
        trn = tr.part(df, start, cal_lo - pd.Timedelta(days=1), H, drop_drives=test_fail)
        cal = tr.part(df, cal_lo, end_y, H)
        cats = tr.categories(trn, 30)
        est, cols = tr.fit(
            "v2", tr.design(trn, cats, "v2"), trn[f"y{H}"].to_numpy(), trn["w"].to_numpy()
        )
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
        iso.fit(
            tr.predict(est, cols, tr.design(cal, cats, "v2")),
            cal[f"y{H}"].to_numpy(),
            sample_weight=cal["w"].to_numpy(),
        )
        for ty in test_years:
            lo, hi = pd.Timestamp(f"{ty}-01-01"), pd.Timestamp(f"{ty}-12-31")
            if lo > df["date"].max():
                continue
            hi = min(hi, df["date"].max())
            te = tr.part(df, lo, hi, H)
            y, w = te[f"y{H}"].to_numpy(), te["w"].to_numpy()
            raw = tr.predict(est, cols, tr.design(te, cats, "v2"))
            p_fixed = iso.predict(raw)
            # rolling recalibration: isotonic refitted on the last quarter before the test year
            rc = tr.part(df, lo - pd.DateOffset(months=3), lo - pd.Timedelta(days=1), H)
            iso2 = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
            iso2.fit(
                tr.predict(est, cols, tr.design(rc, cats, "v2")),
                rc[f"y{H}"].to_numpy(),
                sample_weight=rc["w"].to_numpy(),
            )
            p_roll = iso2.predict(raw)
            res.append(
                {
                    "train_to": Y,
                    "test_year": ty,
                    "years_ahead": ty - Y,
                    "rows": int(len(y)),
                    "fixed": scores(y, p_fixed, w),
                    "rolling": scores(y, p_roll, w),
                }
            )
            log(
                f"train<= {Y}, test {ty}: fixed slope {res[-1]['fixed']['slope']:.2f} "
                f"ECE {res[-1]['fixed']['ece']:.2e}; rolling slope "
                f"{res[-1]['rolling']['slope']:.2f}"
            )
        log(f"Y = {Y}: {time.time() - t:.0f}s")
    (RES / "drift_w16.json").write_text(json.dumps(res, indent=2))


# --------------------------------------------------------------------------- policy effect
def policy() -> None:
    from vmsim import engine, scenarios, worlds
    from vmsim.config import SimConfig
    from vmsim.policies.bam import BAM

    rows = json.loads((RES / "drift_w16.json").read_text())
    slopes = {
        "fixed": float(np.median([r["fixed"]["slope"] for r in rows])),
        "rolling": float(np.median([r["rolling"]["slope"] for r in rows])),
    }
    gammas = {k: 1.0 / v for k, v in slopes.items() if v > 0}
    cfg = scenarios.regime(SimConfig(n_hosts=2_000, horizon_days=365, name="dp"), "A3")
    out = {"median_slope": slopes, "gamma": gammas, "runs": []}
    for seed in range(101, 106):
        prep = engine.prepare(worlds.generate(cfg, seed), cfg)
        base = engine.run(prep, BAM(), budget_frac=0.02)["cost_total"]
        rec = {"seed": seed, "calibrated": base}
        for k, g in gammas.items():
            pred = engine.make_predictor(prep, "miscal", gamma=g)
            rec[k] = engine.run(prep, BAM(), predictor=pred, budget_frac=0.02)["cost_total"]
        out["runs"].append(rec)
        log(rec)
    r = pd.DataFrame(out["runs"])
    out["mean_rel_cost_vs_calibrated"] = {
        k: float(((r[k] - r["calibrated"]) / r["calibrated"]).mean()) for k in gammas
    }
    (RES / "drift_policy_w16.json").write_text(json.dumps(out, indent=2))
    log(out["mean_rel_cost_vs_calibrated"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ensemble", action="store_true")
    ap.add_argument("--drift", action="store_true")
    ap.add_argument("--policy", action="store_true")
    a = ap.parse_args()
    if a.drift:
        drift()
    if a.policy:
        policy()
    if a.ensemble:
        ensemble()
