# Changes after the freeze

Protocol v1.0 and code `v2.0-rc1` were frozen on 4 Oct 2026 (Week 17). Every change after that is listed here with its date, reason, the commit, and which results it affects. Results produced under a change are exploratory unless the change is a bug fix that restores the frozen intent; then the affected runs are repeated for every policy on the same seeds (PROTOCOL section 5, protocol failures).

| Date | Change | Reason | Commit | Results affected |
| --- | --- | --- | --- | --- |
| 4 Oct 2026 | `vmsim/policies/base.py: top_hosts_mask` now passes every VM on an eligible host, instead of the first hosts covering 3 x budget + 200 GB | Bug: a "speed-up only" filter was not exact. VMs the engine skips (no destination, first-fit) left small budgets unfilled: P2 and P1 used about 88% of a 0.5% budget whatever their tau, so the protocol's "use the budget" tuning could not be met. Found in Week 18 P2 tuning; no evaluation run had started. No measurable run-time cost. Regression test `test_threshold_fills_a_small_budget_exactly` | this commit | Week 18 tuning restarted from scratch (3 tuning files deleted); dry run (crash check only) not repeated; pilot and smoke results at 2% unaffected in utilisation (0.95-0.97), and they are not evaluation results |
