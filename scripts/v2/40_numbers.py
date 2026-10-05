"""Week 22, task 2: paper/numbers.tex, every number in the paper as a macro.

Macros are named \\V<Name> with letters only (digits spelled out: B1 at 2% -> BOneTwo). Values are
read from the files that hold them (configs/v2/matrix.yaml, results/v2/*.json and csv,
results/summary/*.json); nothing is typed by hand. A result whose file does not exist yet prints
as "??" and is listed by this script, so a draft can compile before the runs; once results are
frozen, `--strict` fails if any placeholder remains. tests/v2/test_paper_numbers.py fails if the
paper uses a \\V macro this script does not define.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
RES, SUMM = ROOT / "results" / "v2", ROOT / "results" / "summary"
WORDS = "Zero One Two Three Four Five Six Seven Eight Nine".split()
PLACEHOLDER = r"\textbf{??}"


def name(*parts: str) -> str:
    """Macro name from parts: digits spelled out, everything else kept if it is a letter."""
    out = []
    for p in parts:
        for ch in str(p):
            if ch.isdigit():
                out.append(WORDS[int(ch)])
            elif ch.isalpha():
                out.append(ch)
    return "V" + "".join(out)


def pct(x: float, nd: int = 1, sign: bool = True) -> str:
    return f"{100 * x:+.{nd}f}" if sign else f"{100 * x:.{nd}f}"


def load_json(p: Path) -> dict | None:
    return json.loads(p.read_text()) if p.exists() else None


def build() -> tuple[dict[str, str], list[str]]:
    v: dict[str, str] = {}
    missing: list[str] = []

    m = yaml.safe_load((ROOT / "configs/v2/matrix.yaml").read_text())
    sc, conf = m["scale"], m["confirmatory"]
    v["VHosts"] = f"{sc['n_hosts']:,}"
    v["VHorizonDays"] = str(sc["horizon_days"])
    v["VWarmupDays"] = str(sc["warmup_days"])
    v["VEvalSeeds"] = str(m["seeds"]["eval"][1] - m["seeds"]["eval"][0] + 1)
    v["VFamilySize"] = str(len(conf["policies"]) * len(conf["regimes"]) * len(conf["budgets_pct"]))

    q = load_json(RES / "backblaze_quality.json")
    if q:
        v["VDriveDaysM"] = f"{q['drive_days'] / 1e6:.1f}"
        v["VDrives"] = f"{q['drives']:,}"
        v["VDriveFailures"] = f"{q['failures']:,}"

    t = RES / "trace_rho_table.csv"
    if t.exists():
        d = pd.read_csv(t)
        tb = d[d.stat == "tau_b"]
        v["VGOneMaxAbsTauB"] = f"{tb.estimate.abs().max():.3f}"
        v["VGOneMaxLatentUpper"] = f"{tb.latent_high.max():.3f}"

    t2 = RES / "trace_rho_second_table.csv"  # Week 21 second source (cell f), never part of G1
    if t2.exists():
        d = pd.read_csv(t2)
        r = d[
            (d.mapping == "M1")
            & (d.proxy == "risk_platform")
            & (d.weight == "n")
            & (d.stat == "tau_b")
        ].iloc[0]
        v["VSecondTauB"] = f"{r.estimate:+.3f}"
        v["VSecondLatent"] = f"{r.latent:+.3f}"
        v["VSecondLatentHi"] = f"{r.latent_high:+.3f}"

    an = load_json(SUMM / "v1_anomaly.json")
    if an:
        h6 = an["H6"]
        v["VVOneAdvRandom"] = pct(h6["delta_by_accounting_window_days"]["inf"])
        v["VVOneAdvAligned"] = pct(h6["delta_by_window_exact_budgets"]["same_gb"]["30"], 2)
        v["VVOneMedianLeadDays"] = f"{h6['lead_time']['v1_cost_sensitive']['median_lead_days']:.0f}"

    ex = load_json(RES / "bam_exact_check.json")
    if ex:
        v["VBamExactGap"] = pct(ex["sim-A3"]["gap_mean"], 2, sign=False)

    fp = load_json(RES / "f4_theory_params.json")
    if fp:
        v["VSigmaKappaNatural"] = f"{fp['A1']['s_y']:.2f}"
        v["VSigmaPNatural"] = f"{fp['A1']['s_x']:.2f}"

    mm = RES / "model_v2_metrics.csv"
    if mm.exists():
        d = pd.read_csv(mm)
        d = d[(d.h == 30) & (d.calibration == "isotonic")].set_index("model")
        v["VPrAucVOneFeatures"] = f"{d.loc['v1', 'pr_auc']:.4f}"
        v["VPrAucSMART"] = f"{d.loc['v2', 'pr_auc']:.3f}"
        v["VPrAucLogit"] = f"{d.loc['logit', 'pr_auc']:.3f}"
        v["VRocAucSMART"] = f"{d.loc['v2', 'roc_auc']:.3f}"
    mc = load_json(RES / "model_choice.json")
    if mc:
        v["VPrAucEnsembleVal"] = f"{mc['pr_auc_raw']['ensemble']:.3f}"
        v["VPrAucLogitVal"] = f"{mc['pr_auc_raw']['logit']:.3f}"

    th = load_json(RES / "theory_check.json")
    if th:
        v["VTheoryPoints"] = f"{th['points']:,}"
        v["VTheoryMinDeltaNoNoise"] = pct(th["T2_min_delta_cf_no_noise"], 2)

    g2 = load_json(RES / "g2_validation.json")
    if g2:
        v["VVOneRegressionRelErr"] = (
            f"{abs(g2['v1_regression']['cost_sensitive']['rel_diff']):.0e}".replace(
                "e-0", r"\times10^{-"
            )
            + "}"
        )

    pb = load_json(RES / "pilot_w14b.json")
    if pb:
        for cell, key in (("A3@0.02", "AThree"), ("B1@0.02", "BOne")):
            v[f"VPilotSD{key}"] = pct(pb["cells"][cell]["delta_vs_p2_sd"]["P3"], 2, sign=False)

    # results: the confirmatory family (placeholders until the runs exist)
    cf = load_json(SUMM / "confirmatory.json")
    cells = {(c["regime"], c["budget_pct"], c["policy"]): c for c in (cf or {}).get("cells", [])}
    for pol in conf["policies"]:
        for reg in conf["regimes"]:
            for b in conf["budgets_pct"]:
                c = cells.get((reg, float(b), pol))
                base = (pol, reg.replace("-", ""), f"{float(b):g}")
                keys = {
                    name("Delta", *base): None if c is None else pct(c["delta_adjusted"]),
                    name("Holm", *base): None
                    if c is None or c.get("holm_p") is None
                    else f"{c['holm_p']:.3f}",
                    name("CILo", *base): None
                    if c is None
                    else pct((c.get("ci_bca_simultaneous") or c["ci_bca"])[0]),
                    name("CIHi", *base): None
                    if c is None
                    else pct((c.get("ci_bca_simultaneous") or c["ci_bca"])[1]),
                }
                for k, val in keys.items():
                    if val is None:
                        missing.append(k)
                        v[k] = PLACEHOLDER
                    else:
                        v[k] = val
    if cf:
        v["VHolmScope"] = cf["holm_scope"]
        v["VWins"] = str(sum(bool(c.get("win")) for c in cf["cells"]))
    else:
        for k in ("VHolmScope", "VWins"):
            v[k] = PLACEHOLDER
            missing.append(k)
    return v, missing


def render(v: dict[str, str]) -> str:
    bad = [k for k in v if not re.fullmatch(r"V[A-Za-z]+", k)]
    if bad:
        raise ValueError(f"macro names must be letters only: {bad}")
    lines = ["% generated by scripts/v2/40_numbers.py; do not edit"]
    lines += [f"\\newcommand{{\\{k}}}{{{val}\\xspace}}" for k, val in sorted(v.items())]
    return "\\usepackage{xspace}\n" + "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--strict", action="store_true", help="fail if any result is still a placeholder"
    )
    a = ap.parse_args()
    v, missing = build()
    (ROOT / "paper" / "numbers.tex").write_text(render(v))
    print(
        f"{len(v)} macros; {len(missing)} placeholders (results not run yet)"
        if missing
        else f"{len(v)} macros"
    )
    if a.strict and missing:
        sys.exit(f"placeholders remain: {missing[:8]}...")


if __name__ == "__main__":
    main()
