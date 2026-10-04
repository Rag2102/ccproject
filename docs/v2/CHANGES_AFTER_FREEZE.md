# Changes after the freeze

Protocol v1.0 and code `v2.0-rc1` were frozen on 4 Oct 2026 (Week 17). Every change after that is listed here with its date, reason, the commit, and which results it affects. Results produced under a change are exploratory unless the change is a bug fix that restores the frozen intent; then the affected runs are repeated for every policy on the same seeds (PROTOCOL section 5, protocol failures).

| Date | Change | Reason | Commit | Results affected |
| --- | --- | --- | --- | --- |
| 4 Oct 2026 | `vmsim/policies/base.py: top_hosts_mask` now passes every VM on an eligible host, instead of the first hosts covering 3 x budget + 200 GB | Bug: a "speed-up only" filter was not exact. VMs the engine skips (no destination, first-fit) left small budgets unfilled: P2 and P1 used about 88% of a 0.5% budget whatever their tau, so the protocol's "use the budget" tuning could not be met. Found in Week 18 P2 tuning; no evaluation run had started. No measurable run-time cost. Regression test `test_threshold_fills_a_small_budget_exactly` | this commit | Week 18 tuning restarted from scratch (3 tuning files deleted); dry run (crash check only) not repeated; pilot and smoke results at 2% unaffected in utilisation (0.95-0.97), and they are not evaluation results |
| 4 Oct 2026 | `vmsim.entities.azure_table()` reads `data/processed/azure_vms_vmsim.parquet`, an exact extract of the five Azure columns vmsim uses (`scripts/v2/09_azure_extract.py`), instead of the Git LFS CSV | CI checks out without LFS, so the CSV was a pointer file and every simulator test failed. No change to any value: every row, same dtypes, round trip checked; all tests, including the exact v1 regression, pass | ebd5b85 | None (data source only) |

Tags: `protocol-v1.0` and `v2.0-rc1` are on the freeze commit d126174. `v2.0-rc2` (ebd5b85) is rc1 plus the two fixes above, and is the code the Week 18 runs use (each record carries its git SHA).
