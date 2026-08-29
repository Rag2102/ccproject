"""
Task 6/7 -- The two mitigation policies being compared, as plain reusable
functions. Both the illustrative scenarios in 05_policy_design.py and the
full replay simulator in task 8 import this module, so the exact same
decision logic is what gets designed here, validated on hand-built cases,
and then evaluated at scale later -- no drift between "the policy we
designed" and "the policy we tested."

Both policies see the same four inputs at decision time:
  p_fail          : P(failure within the lookahead window)      [task 3]
  ttf_days        : expected time-to-failure, in days            [task 4]
  criticality_wt  : workload criticality weight (0-1)             [task 2]
  migration_cost  : cost of migrating now (resource + customer)   [task 5]
  failure_cost    : cost if this fails unmitigated (customer)     [task 5]
The threshold baseline deliberately uses only p_fail -- that's the point of
the comparison, not an oversight.
"""
import numpy as np

LOOKAHEAD_DAYS = 30      # must match the lookahead used to build p_fail_within_window (task 3)
URGENCY_CAP = 5.0        # max amplification for an imminent expected failure
MIN_TTF_FLOOR_DAYS = 1.0  # avoids a division blow-up as ttf_days -> 0


def urgency_weight(ttf_days, lookahead_days=LOOKAHEAD_DAYS, cap=URGENCY_CAP):
    """
    How much more should the SAME p_fail worry us, given how soon the
    failure is expected relative to our decision lookahead?

    If expected TTF already exceeds the lookahead window, the risk within
    that window is already fully reflected in p_fail_within_window itself
    (a longer TTF naturally implies a lower p_fail from the hazard model) --
    so urgency stays at its neutral value of 1.0, deliberately not
    *discounting* p_fail further, to avoid double-counting the same signal.

    If expected TTF is shorter than the lookahead, there is less room to
    defer the decision to a future reassessment without risking missing
    the failure window entirely, so the same p_fail is weighted up,
    capped at `cap` so a near-zero TTF doesn't blow the term up to infinity.
    """
    ttf = np.maximum(np.asarray(ttf_days, dtype=float), MIN_TTF_FLOOR_DAYS)
    return np.clip(lookahead_days / ttf, 1.0, cap)


def cost_sensitive_decision(p_fail, ttf_days, failure_cost, migration_cost,
                             lookahead_days=LOOKAHEAD_DAYS):
    """
    The policy under test. Migrate iff the expected cost of doing nothing
    (probability-weighted failure cost, urgency-adjusted for how soon that
    failure is expected) exceeds the cost of migrating now.

    `failure_cost` and `migration_cost` are expected to already be on the
    same units (customer-impact-minutes; migration_cost should be the sum
    of its resource + customer components -- see task 5) and already
    incorporate criticality weighting where relevant, so this function
    itself stays a plain expected-cost comparison.
    """
    urgency = urgency_weight(ttf_days, lookahead_days)
    expected_cost_of_inaction = np.asarray(p_fail, dtype=float) * failure_cost * urgency
    migrate = expected_cost_of_inaction > migration_cost
    return {
        "migrate": migrate,
        "expected_cost_of_inaction": expected_cost_of_inaction,
        "migration_cost": np.broadcast_to(migration_cost, expected_cost_of_inaction.shape) if np.ndim(expected_cost_of_inaction) else migration_cost,
        "urgency_weight": urgency,
    }


def threshold_decision(p_fail, threshold):
    """The baseline being benchmarked: migrate iff P(failure) exceeds a
    fixed threshold, full stop -- no urgency, criticality, or cost term."""
    return np.asarray(p_fail, dtype=float) > threshold
