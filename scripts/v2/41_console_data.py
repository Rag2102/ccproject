"""Week 22, task 6: data for the static Console (console/), from results/summary at this commit.

Writes console/data/console.json:
  meta       git SHA, generation time, source directory and whether it is a dry run or the small
             reproduction (the Console then shows a banner: not results)
  crossover  per (regime, budget, policy) in A and E: rho_L, sigma_log_kappa, adjusted Delta,
             BCa CI,
             n, per-seed values; provenance SIMULATED
  rho        the G1 measurement per cell (M1, platform proxy): tau-b, CI, latent rho; MEASURED
  family     the confirmatory cells with Holm p and the win flag
  vs_p0      (S1's other baseline) per (regime, budget, policy) in A and E: the saving against
             never migrating, (C_P0 - C) / C_P0, with its BCa CI and the share of seeds beating
             P0 (34_vs_p0.py); plus the ADR-010 avoidance baselines (37_explore_avoid.py) when
             explore_avoid.json exists, marked exploratory
  rho_all    (S2 Trace Lens, Week 25) every tau-b row of the G1 table and of the second source,
             with the latent value and its interval, plus the pH and C0 reference lines
  matrix     (S4 Run Matrix, Week 25) expected vs present cells of the frozen matrix, n seeds per
             cell, and each scenario card's config hash
  confirm    (S5 Paired Seeds, Week 31) the 30 pre-registered comparisons, the win bar and the SD
             rule's bounds (ADR-007); per-seed values come from crossover and vs_p0
  figures    (S6 Figures, Week 34) results/figures/catalogue.yaml with each figure's status, the
             values of the macros it quotes (paper/numbers.tex) and a PNG preview
             (console/data/figs/, rendered with pdftoppm when it is installed)
--anonymous (double-blind review) drops the git SHA and every link that names the repository or
the author; the page then shows "anonymised".
The Console reads only this file (ADR-002: read-only, never blocks the paper).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
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
                    "sd": c.get("delta_sd"),  # the SD rule's statistic (unadjusted, 30_stats)
                    "family": c["family"],
                    "provenance": "SIMULATED",
                }
            )
    # S1 against never migrating (ADR-005 companion) and the exploratory avoidance baselines
    out["vs_p0"] = []
    for fname in ("vs_p0.json", "explore_avoid.json"):
        f = summ / fname
        if not f.exists():
            continue
        for c in json.loads(f.read_text())["cells"]:
            reg = c["regime"]
            if reg[0] not in "AE" or (fname != "vs_p0.json" and "avoid" not in c["policy"]):
                continue
            out["vs_p0"].append(
                {
                    "regime": reg,
                    "rho_latent": scenarios.A_LATENT.get(reg, 0.0),
                    "kappa_sigma": scenarios.E_SIGMA.get(reg),
                    "budget_pct": c["budget_pct"],
                    "policy": c["policy"],
                    "saving": c["saving_vs_p0_mean"],
                    "ci": c["ci_bca"],
                    "n": c["n_seeds"],
                    "share_beating_p0": c["share_seeds_beating_p0"],
                    "per_seed": c.get("per_seed", []),
                    "family": c.get("family", "descriptive"),
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
    g1f = res / "trace_rho.json"
    g1 = json.loads(g1f.read_text()) if g1f.exists() else {}
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
    # S5 Paired Seeds: the confirmatory family's definition, the win bar and the SD rule
    conf = m["confirmatory"]
    out["confirm"] = {
        "policies": conf["policies"],
        "regimes": conf["regimes"],
        "budgets": [float(b) for b in conf["budgets_pct"]],
        "delta_bar": 0.01,
        "sd_bound": {"30": 0.016, "50": 0.021},  # 30_stats.SD_BOUND, PROTOCOL section 6
    }

    # S6 Figures: the catalogue, each figure's status and the macro values its caption quotes
    nums = {}
    nt = ROOT / "paper" / "numbers.tex"
    if nt.exists():
        for k, val in re.findall(
            r"\\newcommand\{\\(V[A-Za-z]+)\}\{(.*?)\\xspace\}", nt.read_text()
        ):
            nums[k] = val
    cat = ROOT / "results" / "figures" / "catalogue.yaml"
    figs_dir = ROOT / "console" / "data" / "figs"
    figs_dir.mkdir(parents=True, exist_ok=True)
    out["figures"] = []
    for f in yaml.safe_load(cat.read_text()) if cat.exists() else []:
        pdf = ROOT / "results" / "figures" / f["file"]
        have_src = (ROOT / f["source"]).exists()
        png = None
        if pdf.exists() and have_src and shutil.which("pdftoppm"):
            stem = figs_dir / f["id"]
            subprocess.run(
                ["pdftoppm", "-png", "-r", "90", "-singlefile", str(pdf), str(stem)], check=True
            )
            png = f"data/figs/{f['id']}.png"
        out["figures"].append(
            {
                **{k: f[k] for k in ("id", "title", "takeaway", "file", "source", "make")},
                "provenance": f.get("provenance", "SIMULATED"),
                "status": "results" if have_src and pdf.exists() else "pending",
                "png": png,
                "macros": {
                    k: ("??" if "??" in nums.get(k, "??") else re.sub(r"\{,\}", ",", nums[k]))
                    for k in f.get("macros", [])
                },
            }
        )

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
