"""Export the v2 ensemble (ADR-006's winner) for the web demo: models/v2_ensemble/.

Refits the 20 bootstrap members exactly as scripts/v2/22_model_choice.py did (Week 7's split, H =
30, v2 features, Poisson bootstrap over training drives, seed 16), fits one isotonic map on the
validation period to the mean of the members' raw probabilities (ADR-006, step 3), and saves:
  meta.joblib        feature order, drive-model categories, isotonic map, capacity per model,
                     validation and test PR-AUC of the exported ensemble
  member_XX.joblib   one HistGradientBoostingClassifier each (compressed)
Needs data/v2/features (local only; the web app needs only the exported files).
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("tr", ROOT / "scripts/v2/12_train.py")
tr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tr)

H = 30
N_MODELS = 20
OUT = ROOT / "models" / "v2_ensemble"


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def main() -> None:
    df = tr.load()
    sp = tr.split_dates(df)
    test_fail = set(df.loc[df["fail_date"].between(*sp["test"]), "serial_number"].unique())
    trn = tr.part(df, *sp["train"], H, drop_drives=test_fail)
    val = tr.part(df, *sp["val"], H)
    tst = tr.part(df, *sp["test"], H)
    cats = tr.categories(trn, 30)
    x_tr, x_va, x_te = (tr.design(s, cats, "v2") for s in (trn, val, tst))
    y_tr, w_tr = trn[f"y{H}"].to_numpy(), trn["w"].to_numpy()
    codes, uniq = pd.factorize(trn["serial_number"])
    rng = np.random.default_rng(16)  # same draws as Weeks 16 and 17
    OUT.mkdir(parents=True, exist_ok=True)
    va_raw, te_raw = [], []
    for k in range(N_MODELS):
        t = time.time()
        bw = w_tr * rng.poisson(1.0, len(uniq))[codes]
        keep = bw > 0
        est, cols = tr.fit("v2", x_tr[keep], y_tr[keep], bw[keep])
        va_raw.append(tr.predict(est, cols, x_va))
        te_raw.append(tr.predict(est, cols, x_te))
        joblib.dump(est, OUT / f"member_{k:02d}.joblib", compress=3)
        log(f"member {k + 1}/{N_MODELS}: {time.time() - t:.0f}s")
    va_mean, te_mean = np.mean(va_raw, 0), np.mean(te_raw, 0)
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
    iso.fit(va_mean, val[f"y{H}"].to_numpy(), sample_weight=val["w"].to_numpy())
    m_va = tr.metrics(val[f"y{H}"].to_numpy(), va_mean, val["w"].to_numpy())
    m_te = tr.metrics(tst[f"y{H}"].to_numpy(), iso.predict(te_mean), tst["w"].to_numpy())
    cap = trn.groupby("model_key")["capacity_tb"].median()
    meta = {
        "h_days": H,
        "features": list(x_tr.columns),
        "numeric": list(tr.NUMERIC),
        "categories": cats,
        "isotonic": iso,
        "n_members": N_MODELS,
        "capacity_by_model": {k: float(cap[k]) for k in cats if k in cap},
        "validation_pr_auc_raw": float(m_va["pr_auc"]),
        "test_pr_auc": float(m_te["pr_auc"]),
        "test_roc_auc": float(m_te["roc_auc"]),
        "test_base_rate": float(m_te["base_rate"]),
        "split": {
            k: [str(pd.Timestamp(a).date()), str(pd.Timestamp(b).date())]
            for k, (a, b) in sp.items()
        },
        "source": "scripts/v2/25_export_ensemble.py (ADR-006 winner)",
    }
    joblib.dump(meta, OUT / "meta.joblib", compress=3)
    size = sum(f.stat().st_size for f in OUT.iterdir()) / 1e6
    log(
        f"validation PR-AUC (raw mean) {m_va['pr_auc']:.4f}; test PR-AUC {m_te['pr_auc']:.4f}, "
        f"ROC-AUC {m_te['roc_auc']:.4f}; {size:.1f} MB in {OUT}"
    )


if __name__ == "__main__":
    sys.exit(main())
