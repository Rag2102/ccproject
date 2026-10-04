# Changes after the freeze

Protocol v1.0 and code `v2.0-rc1` were frozen on 4 Oct 2026 (Week 17). Every change after that is listed here with its date, reason, the commit, and which results it affects. Results produced under a change are exploratory unless the change is a bug fix that restores the frozen intent; then the affected runs are repeated for every policy on the same seeds (PROTOCOL section 5, protocol failures).

| Date | Change | Reason | Commit | Results affected |
| --- | --- | --- | --- | --- |
| 4 Oct 2026 | `vmsim/policies/base.py: top_hosts_mask` now passes every VM on an eligible host, instead of the first hosts covering 3 x budget + 200 GB | Bug: a "speed-up only" filter was not exact. VMs the engine skips (no destination, first-fit) left small budgets unfilled: P2 and P1 used about 88% of a 0.5% budget whatever their tau, so the protocol's "use the budget" tuning could not be met. Found in Week 18 P2 tuning; no evaluation run had started. No measurable run-time cost. Regression test `test_threshold_fills_a_small_budget_exactly` | this commit | Week 18 tuning restarted from scratch (3 tuning files deleted); dry run (crash check only) not repeated; pilot and smoke results at 2% unaffected in utilisation (0.95-0.97), and they are not evaluation results |
| 4 Oct 2026 | `vmsim.entities.azure_table()` reads `data/processed/azure_vms_vmsim.parquet`, an exact extract of the five Azure columns vmsim uses (`scripts/v2/09_azure_extract.py`), instead of the Git LFS CSV | CI checks out without LFS, so the CSV was a pointer file and every simulator test failed. No change to any value: every row, same dtypes, round trip checked; all tests, including the exact v1 regression, pass | ebd5b85 | None (data source only) |

Tags: `protocol-v1.0` and `v2.0-rc1` are on the freeze commit d126174. `v2.0-rc2` (ebd5b85) is rc1 plus the two fixes above, and is the code the Week 18 runs use (each record carries its git SHA).

## Week 19-20 preparation (5 Oct 2026, before any evaluation run)

| Date | Change | Reason | Commit | Results affected |
| --- | --- | --- | --- | --- |
| 5 Oct 2026 | `MigrationConfig.true_bw_factor`, `true_dirty_factor` (default 1.0): the realised migrations use these factors, while policies' estimates stay nominal | Week 20's cost-model error (PROTOCOL section 9, "bandwidth and dirty rate ±50%") needs reality to differ from what the policies assume; scaling the config alone would change both | this commit | None at the defaults: the code path is unchanged when both are 1.0 (tests, v1 regression and determinism pass) |
| 5 Oct 2026 | `tune_p2(..., predictor=None)`: optional predictor for tuning | Owner (5 Oct): P2 is retuned per robustness setting, on the scores it will see | this commit | None at the default |
| 5 Oct 2026 | Model-based worlds (ADR-008) moved from Week 20 to after Week 21 | Owner decision: about a day of work (full daily features, ensemble scoring, drive replay) | — | Week 20 robustness without that row; exploratory either way |
| 5 Oct 2026 | Morris design fixed in `configs/v2/w20.yaml`: 10 factors, r = 20, 4 levels, A3, eval seeds 1-3; P2 retuned at each point with a fast tuner (2 dev seeds, 8 bisection steps, the order chosen in Week 18) | PROTOCOL section 9 named the factors but not how P2 is handled; a full tune per point (220 points) would take about 40 core-hours | — | Week 20 sensitivity (exploratory) |
| 5 Oct 2026 | Morris implemented in the repo (`vmsim/morris.py`), not SALib | Owner decision: no new dependency; Sobol only if compute allows | — | None |

Also recorded: testing the Week 19 scripts ran them on the Week 17 dry run (eval seeds 1-2, code from before the pre-filter fix). Comparisons on those two seeds were displayed. They feed no decision and are superseded by the Week 18-19 runs.
