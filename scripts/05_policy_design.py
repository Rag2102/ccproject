"""
Task 6/7 -- Cost-sensitive mitigation policy vs. probability-threshold
baseline. This is the actual contribution of the project (task 6) and its
benchmark (task 7); both were small and tightly coupled enough to build and
validate together.

Two kinds of verification, on purpose, before the full replay simulator
(task 8) is built:
  1. Hand-built scenarios where we know, by construction, what a sensible
     policy should do -- catches a broken decision rule cheaply, before
     it's buried inside a simulator.
  2. A full "decision surface" over every real host-risk state (task 3/4's
     lookup tables) crossed with every real representative VM profile
     (task 2/5's cost data) -- not a temporal simulation yet, just: for
     every state the fleet can actually be in, what does each policy do,
     and where do they disagree?

Run from the project root: python3 scripts/05_policy_design.py
"""
import numpy as np
import pandas as pd
from pathlib import Path
from policy import cost_sensitive_decision, threshold_decision, urgency_weight

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"

# ---------------------------------------------------------------------------
# 1. Hand-built scenarios -- do the two policies diverge exactly where the
#    problem statement claims they should?
# ---------------------------------------------------------------------------
scenarios = pd.DataFrame([
    # name, p_fail, ttf_days, failure_cost, migration_cost, expected_story
    dict(name="Obvious migrate: high risk, imminent, critical, cheap to move",
         p_fail=0.05, ttf_days=3, failure_cost=10.0, migration_cost=0.05),
    dict(name="Obvious skip: negligible risk, distant, batch workload",
         p_fail=0.0002, ttf_days=1500, failure_cost=3.0, migration_cost=0.03),
    dict(name="TTF-awareness case: modest p_fail but failure is imminent",
         p_fail=0.01, ttf_days=2, failure_cost=6.0, migration_cost=0.20),
    dict(name="Cost-awareness case: p_fail just above a typical threshold, "
              "but VM is huge and low-criticality, failure is distant",
         p_fail=0.006, ttf_days=200, failure_cost=3.0, migration_cost=1.5),
    dict(name="Criticality-awareness case: same p_fail as above, but "
              "high-criticality + cheap to move",
         p_fail=0.006, ttf_days=200, failure_cost=10.0, migration_cost=0.05),
])
BASELINE_TAU_ILLUSTRATIVE = 0.005  # a plausible round-number ops threshold, for illustration only

cs = cost_sensitive_decision(scenarios["p_fail"], scenarios["ttf_days"],
                              scenarios["failure_cost"], scenarios["migration_cost"])
scenarios["cost_sensitive_migrate"] = cs["migrate"]
scenarios["expected_cost_of_inaction"] = cs["expected_cost_of_inaction"].round(4)
scenarios["urgency_weight"] = cs["urgency_weight"].round(2)
scenarios["threshold_migrate"] = threshold_decision(scenarios["p_fail"], BASELINE_TAU_ILLUSTRATIVE)
scenarios["policies_agree"] = scenarios["cost_sensitive_migrate"] == scenarios["threshold_migrate"]

print("=" * 100)
print(f"HAND-BUILT SCENARIOS (baseline threshold tau={BASELINE_TAU_ILLUSTRATIVE} for illustration)")
print("=" * 100)
for _, r in scenarios.iterrows():
    print(f"\n[{r['name']}]")
    print(f"  p_fail={r['p_fail']:.4f}  ttf={r['ttf_days']:.0f}d  failure_cost={r['failure_cost']:.1f}  "
          f"migration_cost={r['migration_cost']:.3f}  urgency={r['urgency_weight']:.2f}x")
    print(f"  expected_cost_of_inaction={r['expected_cost_of_inaction']:.4f} vs migration_cost={r['migration_cost']:.3f}")
    print(f"  -> cost-sensitive: {'MIGRATE' if r['cost_sensitive_migrate'] else 'wait':7s} | "
          f"threshold(tau={BASELINE_TAU_ILLUSTRATIVE}): {'MIGRATE' if r['threshold_migrate'] else 'wait':7s} | "
          f"{'AGREE' if r['policies_agree'] else 'DISAGREE'}")

scenarios.to_csv(PROCESSED / "policy_scenarios.csv", index=False)

# ---------------------------------------------------------------------------
# 2. Full decision surface: every real host-risk state x every real
#    representative VM cost profile
# ---------------------------------------------------------------------------
ttf_lookup = pd.read_csv(PROCESSED / "ttf_lookup_table.csv")
vm_costs = pd.read_csv(PROCESSED / "azure_vms_with_costs.csv.gz")

vm_profiles = vm_costs.groupby(["size_tier", "criticality_tier"]).agg(
    n_vms=("vm_id", "size"),
    criticality_weight=("criticality_weight", "median"),
    migration_resource_cost_min=("migration_resource_cost_min", "median"),
    migration_customer_cost_min=("migration_customer_cost_min", "median"),
    failure_customer_cost_min=("failure_customer_cost_min", "median"),
).reset_index()
vm_profiles["total_migration_cost_min"] = (
    vm_profiles["migration_resource_cost_min"] + vm_profiles["migration_customer_cost_min"]
)
print(f"\n\nRepresentative VM profiles (median cost per size x criticality bucket): {len(vm_profiles)}")
print(vm_profiles.to_string(index=False))

# Baseline threshold, chosen empirically rather than by hand: the 95th
# percentile of P(failure within window) across every real host-risk state
# this fleet can actually be in -- "flag the riskiest 5% of observations,"
# a common ops heuristic, and a defensible default for the comparison in
# task 8/9 (which will also sweep tau explicitly, since any single-number
# threshold choice is somewhat arbitrary by nature -- that arbitrariness is
# itself part of what this project argues against).
tau_default = ttf_lookup["p_fail_within_window"].quantile(0.95)
print(f"\nBaseline threshold (95th percentile of real host risk states): tau = {tau_default:.5f}")

grid = ttf_lookup.merge(vm_profiles, how="cross")
cs_grid = cost_sensitive_decision(
    grid["p_fail_within_window"], grid["expected_ttf_days"],
    grid["failure_customer_cost_min"], grid["total_migration_cost_min"],
)
grid["cost_sensitive_migrate"] = cs_grid["migrate"]
grid["threshold_migrate"] = threshold_decision(grid["p_fail_within_window"], tau_default)

n = len(grid)
agree = (grid["cost_sensitive_migrate"] == grid["threshold_migrate"]).mean()
cs_only = (grid["cost_sensitive_migrate"] & ~grid["threshold_migrate"]).mean()
thresh_only = (~grid["cost_sensitive_migrate"] & grid["threshold_migrate"]).mean()

print(f"\nDecision surface: {n:,} (host risk state x VM profile) combinations")
print(f"  Policies agree:                              {agree:.2%}")
print(f"  Cost-sensitive migrates, threshold doesn't:  {cs_only:.2%}  "
      f"(policy catches something the flat threshold misses)")
print(f"  Threshold migrates, cost-sensitive doesn't:  {thresh_only:.2%}  "
      f"(policy avoids a migration the flat threshold would trigger)")

print("\nWhat characterizes each disagreement type:")
for label, mask in [("Cost-sensitive migrates, threshold doesn't", grid["cost_sensitive_migrate"] & ~grid["threshold_migrate"]),
                     ("Threshold migrates, cost-sensitive doesn't", ~grid["cost_sensitive_migrate"] & grid["threshold_migrate"])]:
    sub = grid[mask]
    if len(sub) == 0:
        print(f"  {label}: none")
        continue
    print(f"  {label} (n={len(sub):,}):")
    print(f"    mean expected_ttf_days={sub['expected_ttf_days'].mean():.0f}, "
          f"criticality_tier mix={sub['criticality_tier'].value_counts(normalize=True).round(2).to_dict()}, "
          f"size_tier mix={sub['size_tier'].value_counts(normalize=True).round(2).to_dict()}")

grid.to_csv(PROCESSED / "policy_decision_surface.csv", index=False)
print(f"\nSaved -> data/processed/policy_decision_surface.csv ({n:,} rows)")
print("Saved -> data/processed/policy_scenarios.csv")
print("\nDone.")
