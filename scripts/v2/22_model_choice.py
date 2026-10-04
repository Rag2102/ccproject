"""Model choice for the simulator (ADR-006): validation PR-AUC of boosted, logit and ensemble.

Rule (fixed in ADR-006 before this ran): drive-day-weighted PR-AUC on Week 7's validation period
at H = 30, on raw scores (the isotonic maps are fitted on this period). The ensemble's raw score is
the mean of its 20 members' raw probabilities; members are refitted exactly as in Week 16
(scripts/v2/21_uncertainty_drift.py, bootstrap seed 16). Winner: highest PR-AUC, unless the 95%
interval of the difference between the top two (Poisson bootstrap over drives, 1,000 replicates)
contains 0, in which case the simpler one (logit < boosted < ensemble).

Writes results/v2/model_choice.json.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("tr", ROOT / "scripts/v2/12_train.py")
tr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tr)

H = 30
N_MODELS = 20
SIMPLICITY = ["logit", "boosted", "ensemble"]


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def main() -> None:
    df = tr.load()
    sp = tr.split_dates(df)
    test_fail = set(df.loc[df["fail_date"].between(*sp["test"]), "serial_number"].unique())
    trn = tr.part(df, *sp["train"], H, drop_drives=test_fail)
    val = tr.part(df, *sp["val"], H)
    y_va, w_va = val[f"y{H}"].to_numpy(), val["w"].to_numpy()
    log(f"train {len(trn):,} rows, validation {len(val):,} rows")

    raw = {}
    for name, f in (("boosted", "v2_h30.joblib"), ("logit", "logit_h30.joblib")):
        m = joblib.load(tr.MODELS / f)
        kind = "logit" if name == "logit" else "v2"
        raw[name] = tr.predict(m["model"], m["cols"], tr.design(val, m["cats"], kind))

    cats = tr.categories(trn, 30)
    x_tr, x_va = tr.design(trn, cats, "v2"), tr.design(val, cats, "v2")
    y_tr, w_tr = trn[f"y{H}"].to_numpy(), trn["w"].to_numpy()
    codes, uniq = pd.factorize(trn["serial_number"])
    rng = np.random.default_rng(16)  # same draws as Week 16
    members = []
    for k in range(N_MODELS):
        t = time.time()
        bw = w_tr * rng.poisson(1.0, len(uniq))[codes]
        keep = bw > 0
        est, cols = tr.fit("v2", x_tr[keep], y_tr[keep], bw[keep])
        members.append(tr.predict(est, cols, x_va))
        log(f"ensemble member {k + 1}/{N_MODELS}: {time.time() - t:.0f}s")
    raw["ensemble"] = np.mean(members, axis=0)

    point = {k: float(tr.metrics(y_va, p, w_va)["pr_auc"]) for k, p in raw.items()}
    log(f"validation PR-AUC (raw): {point}")

    # paired bootstrap over drives, same replicates for every candidate
    dcodes, duniq = pd.factorize(val["serial_number"])
    scored = {k: tr.Scored(y_va, p) for k, p in raw.items()}
    brng = np.random.default_rng(tr.SEED)
    reps = {k: np.empty(tr.N_BOOT) for k in raw}
    for r in range(tr.N_BOOT):
        bw = w_va * brng.poisson(1.0, len(duniq))[dcodes]
        for k, sc in scored.items():
            reps[k][r] = sc.metrics(bw)["pr_auc"]
    ci = {k: [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))] for k, v in reps.items()}

    ranked = sorted(point, key=point.get, reverse=True)
    first, second = ranked[0], ranked[1]
    d = reps[first] - reps[second]
    d_ci = [float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))]
    separated = d_ci[0] > 0
    winner = first if separated else min(first, second, key=SIMPLICITY.index)
    out = {
        "rule": "ADR-006",
        "h": H,
        "validation": [str(pd.Timestamp(x).date()) for x in sp["val"]],
        "validation_rows": int(len(y_va)),
        "pr_auc_raw": point,
        "pr_auc_raw_ci95": ci,
        "ranking": ranked,
        "top_two_difference_ci95": {"pair": [first, second], "ci": d_ci},
        "separated": bool(separated),
        "winner": winner,
    }
    (ROOT / "results" / "v2" / "model_choice.json").write_text(json.dumps(out, indent=2))
    log(f"winner: {winner} (top two {first} vs {second}, difference CI {d_ci})")


if __name__ == "__main__":
    main()
