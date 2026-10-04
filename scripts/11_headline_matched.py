"""
Adds the matched-budget threshold row to data/processed/simulation_headline_summary.csv.

The v1 summary table held only two rows: the cost-sensitive policy and the
*naive* threshold (tau = 0.0073, 95th percentile of host risk). The live demo
headed the threshold column "matched budget", which was wrong: the matched-
budget comparison (the fair one, -3.1 %) lives in simulation_results_per_host.csv
(outcome_threshold_matched / cost_threshold_matched) and was never put in the
table. This script recomputes all three rows from the per-host file, checks
that the two existing rows reproduce exactly, and writes the three-row table.

Run from scripts/:  python3 11_headline_matched.py
"""
import csv
from pathlib import Path

PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"
PER_HOST = PROCESSED / "simulation_results_per_host.csv"
OUT = PROCESSED / "simulation_headline_summary.csv"

COLS = ["necessary_migrations", "customer_impacting_failures", "unnecessary_migrations",
        "correct_inactions", "total_migrations", "customer_impacting_failure_rate",
        "unnecessary_migration_rate", "total_cost_impact_min"]
POLICIES = {"cost_sensitive": "cost_sensitive", "threshold": "threshold",
            "threshold_matched": "threshold_matched"}


def summarize(rows, suffix):
    counts = {"necessary_migration": 0, "customer_impacting_failure": 0,
              "unnecessary_migration": 0, "correct_inaction": 0}
    cost = 0.0
    for r in rows:
        counts[r[f"outcome_{suffix}"]] += 1
        cost += float(r[f"cost_{suffix}"] or 0.0)
    failed = counts["necessary_migration"] + counts["customer_impacting_failure"]
    healthy = counts["unnecessary_migration"] + counts["correct_inaction"]
    return {
        "necessary_migrations": float(counts["necessary_migration"]),
        "customer_impacting_failures": float(counts["customer_impacting_failure"]),
        "unnecessary_migrations": float(counts["unnecessary_migration"]),
        "correct_inactions": float(counts["correct_inaction"]),
        "total_migrations": float(counts["necessary_migration"] + counts["unnecessary_migration"]),
        "customer_impacting_failure_rate": counts["customer_impacting_failure"] / failed,
        "unnecessary_migration_rate": counts["unnecessary_migration"] / healthy,
        "total_cost_impact_min": cost,
    }


def main():
    rows = list(csv.DictReader(open(PER_HOST)))
    new = {name: summarize(rows, name) for name in POLICIES}
    old = {r[""]: r for r in csv.DictReader(open(OUT))}
    for name in ("cost_sensitive", "threshold"):
        for c in COLS:
            assert abs(float(old[name][c]) - new[name][c]) <= 1e-6 * max(1.0, abs(new[name][c])), (name, c)
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([""] + COLS)
        for name in POLICIES:
            w.writerow([name] + [repr(new[name][c]) for c in COLS])
    print("existing rows reproduce exactly; wrote", OUT)
    for name in POLICIES:
        print(name, int(new[name]["total_migrations"]), round(new[name]["total_cost_impact_min"], 1))


if __name__ == "__main__":
    main()
