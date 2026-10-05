"""Week 22, task 6: data for the static Console (console/), from results/summary at this commit.

Writes console/data/console.json:
  meta       git SHA, generation time, source directory and whether it is a dry run or the small
             reproduction (the Console then shows a banner: not results)
  crossover  per (regime, budget, policy) in A and E: rho_L, sigma_log_kappa, adjusted Delta,
             BCa CI,
             n, per-seed values; provenance SIMULATED
  rho        the G1 measurement per cell (M1, platform proxy): tau-b, CI, latent rho; MEASURED
  family     the confirmatory cells with Holm p and the win flag
  rho_all    (S2 Trace Lens, Week 25) every tau-b row of the G1 table and of the second source,
             with the latent value and its interval, plus the pH and C0 reference lines
  matrix     (S4 Run Matrix, Week 25) expected vs present cells of the frozen matrix, n seeds per
             cell, and each scenario card's config hash
--anonymous (double-blind review) drops the git SHA and every link that names the repository or
the author; the page then shows "anonymised".
The Console reads only this file (ADR-002: read-only, never blocks the paper).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vmsim import scenarios  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", choices=["summary", "dryrun", "small"], default="summary")
    ap.add_argument("--anonymous", action="store_true", help="double-blind build: no SHA, no links")
    a = ap.parse_args()
    summ = {
        "summary": ROOT / "results" / "summary",
        "dryrun": ROOT / "results" / "dryrun_summary",
        "small": ROOT / "results" / "small" / "summary",
    }[a.source]
    sha = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    out = {
        "meta": {
            "git_sha": sha,
            "generated": time.strftime("%Y-%m-%d %H:%M"),
            "source": a.source,
            "results": a.source == "summary",
            "anonymous": a.anonymous,
            "policy_lab_url": None if a.anonymous else "https://ccproject-8twf.onrender.com/#demo",
        },
        "crossover": [],
        "rho": [],
        "family": [],
    }
    for g in ("A", "E"):
        f = summ / f"{g}.json"
        if not f.exists():
            continue
        for c in json.loads(f.read_text())["cells"]:
            reg = c["regime"]
            out["crossover"].append(
                {
                    "regime": reg,
                    "rho_latent": scenarios.A_LATENT.get(reg, 0.0),
                    "kappa_sigma": scenarios.E_SIGMA.get(reg),
                    "budget_pct": c["budget_pct"],
                    "policy": c["policy"],
                    "delta": c["delta_adjusted"],
                    "ci": c["ci_bca"],
                    "n": c["n_seeds"],
                    "per_seed": c.get("per_seed_adjusted", []),
                    "family": c["family"],
                    "provenance": "SIMULATED",
                }
            )
    cf = summ / "confirmatory.json"
    if cf.exists():
        d = json.loads(cf.read_text())
        keys = ("regime", "budget_pct", "policy", "delta_adjusted", "ci_bca", "holm_p", "win")
        out["family"] = [{k: c.get(k) for k in (*keys, "n_seeds")} for c in d["cells"]]
        out["meta"]["holm_scope"] = d["holm_scope"]
    t = ROOT / "results" / "v2" / "trace_rho_table.csv"
    if t.exists():
        d = pd.read_csv(t)
        d = d[
            (d.mapping == "M1")
            & (d.proxy == "risk_platform")
            & (d.weight == "n")
            & (d.stat == "tau_b")
        ]
        out["rho"] = [
            {
                "cell": r.cell,
                "tau_b": r.estimate,
                "ci": [r.ci_low, r.ci_high],
                "rho_latent": r.latent,
                "provenance": "MEASURED",
                "source": "Google 2019, G1_decision.md",
            }
            for r in d.itertuples()
        ]
    # S2 Trace Lens: every tau-b row, G1 cells and the separately analysed second source
    res = ROOT / "results" / "v2"
    g1 = json.loads((res / "trace_rho.json").read_text()) if (res / "trace_rho.json").exists() else {}
    out["meta"]["pH_latent"] = g1.get("pH_latent")
    out["meta"]["c0_latent"] = g1.get("c0_latent")
    out["rho_all"] = []
    for fname, second in (("trace_rho_table.csv", False), ("trace_rho_second_table.csv", True)):
        if not (res / fname).exists():
            continue
        d = pd.read_csv(res / fname)
        for r in d[d.stat == "tau_b"].itertuples():
            out["rho_all"].append(
                {
                    "cell": r.cell,
                    "mapping": r.mapping,
                    "proxy": r.proxy,
                    "weight": r.weight,
                    "tau_b": r.estimate,
                    "ci": [r.ci_low, r.ci_high],
                    "latent": r.latent,
                    "latent_ci": [r.latent_low, r.latent_high],
                    "second_source": second,
                    "provenance": "MEASURED",
                }
            )

    # S4 Run Matrix: expected vs present cells, seeds per cell, card hashes
    mfile = "matrix_small.yaml" if a.source == "small" else "matrix.yaml"
    m = yaml.safe_load((ROOT / "configs" / "v2" / mfile).read_text())
    n_seeds = m["seeds"]["eval"][1] - m["seeds"]["eval"][0] + 1
    present = {}
    for f in sorted(summ.glob("[A-E].json")):
        for c in json.loads(f.read_text())["cells"]:
            present[(c["regime"], float(c["budget_pct"]), c["policy"])] = c["n_seeds"]
    cards = {}
    for f in sorted((ROOT / "configs" / "v2" / "cards").glob("*.yaml")):
        cd = yaml.safe_load(f.read_text())
        cards[cd["id"]] = {"config_hash": cd.get("config_hash"), "provenance": cd.get("provenance")}
    out["matrix"] = {
        "expected_seeds": n_seeds,
        "budgets": m["budgets_pct"],
        "policies": [p for p in m["policies"] if p not in ("P0", "P2")],
        "groups": {g: regs for g, regs in m["regimes"].items()},
        "present": [
            {"regime": r, "budget_pct": b, "policy": p, "n_seeds": n}
            for (r, b, p), n in sorted(present.items())
        ],
        "cards": cards,
    }
    if a.anonymous:
        out["meta"]["git_sha"] = "anonymised"

    dest = ROOT / "console" / "data"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "console.json").write_text(json.dumps(out, indent=1, default=float))
    n_cx, n_rho = len(out["crossover"]), len(out["rho"])
    print(
        f"{n_cx} crossover cells, {n_rho} rho cells, source {a.source} -> console/data/console.json"
    )


if __name__ == "__main__":
    main()
