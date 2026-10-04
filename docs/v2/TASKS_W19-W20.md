# Tasks, Weeks 19-20

From the v5 week cards for W19 and W20 (plan page 20). Prepared on 5 Oct 2026, ahead of the calendar (W19 starts 8 Feb 2027). `[x]` = done and checked; `[~]` = built, waiting for the runs; `[ ]` = not done.

**The runs have not happened yet.** Weeks 18, 19 and 20 are launched together by `scripts/v2/run_overnight.sh`, about 12 hours on 8 cores. Everything below is built and smoke-tested, and the analysis follows the protocol's order: the A and E results paragraph (Week 18) is written before the B and C numbers are opened.

## Week 19 (8-14 Feb): realistic B1, B2 and adversarial C; Pareto frontiers

- [~] Run B1 at three calibrations (B1-low, B1, B1-high), B2, C and D: all policies, 4 budgets, eval seeds 1-30 (`scripts/v2/run_w19.sh`)
- [~] Pareto frontiers (`scripts/v2/27_pareto.py` → `results/summary/pareto.json`, F5 `results/figures/v2_F5_pareto.pdf`):
  - missed failures against migrations;
  - total cost against budget;
  - each curve summarised by its area, normalised by P0's cost.
- [~] Family-wide Holm over all 30 confirmatory comparisons (`30_stats.py --groups A E B C D`; the scope is marked "complete" only when all 30 exist)
- [~] Protocol failures (`scripts/v2/32_protocol_check.py`): completeness, overspend, provenance, plus a sample re-run with the engine's invariant checks; exit code 1 on any failure
- [~] Table 3 by script (`scripts/v2/28_table3.py` → `paper/tables/table3.tex`, `results/summary/table3.csv`); F5
- [ ] Results paragraphs for B and C, and RQ1 restated (after the runs, and after the A and E paragraph)

## Week 20 (15-21 Feb): ablations, robustness and global sensitivity

- [~] Ablations (`configs/v2/w20.yaml`, `scripts/v2/26_run_w20.py --phase ablate`):
  - BAM variants: without urgency, without criticality, with uniform migration cost, p-only, BAM-time, BAM-cost;
  - regimes A1, A3, A5 and B1, at 1% and 2%, seeds 1-30;
  - each compared with full BAM and with P2 from the main matrix (F6).
- [~] Robustness (`--phase rtune`, `--phase robust`):
  - 16 settings: bandwidth and dirty-rate error ±50%, γ ∈ {0.5, 2}, noise σ ∈ {0.25, 0.5, 1, 2}, H ∈ {7, 14}, non-disk hazard 0× and 3×, flat and steep tier weights;
  - regimes A3 and B1 at 2%, all policies;
  - **P2 retuned per setting** (owner).
  - F7 heatmap: bandwidth error × miscalibration on A3.
  - New engine knobs: `true_bw_factor` and `true_dirty_factor` (the realised migrations differ from the policies' estimates).
- [~] Global sensitivity (`--phase morris`; `vmsim/morris.py`, in the repo, owner):
  - Morris screening, 10 factors, r = 20 (220 points), on A3;
  - P2 retuned at each point with a fast tuner;
  - output: the ranking by μ* with σ (`results/summary/w20_morris.json`, `results/figures/v2_morris.pdf`).
- [~] Failure analysis (`--phase failure`): where BAM loses, by host age, day-0 risk and tier mix, for each budget (A3 and B1, seeds 1-5)
- [~] Analysis script: `scripts/v2/29_w20_analysis.py` (F6, F7, Morris, failure analysis)
- [ ] Threats-to-validity update and the two or three assumptions the conclusions depend on most (after the runs)
- [x] Model-based worlds: **deferred past Week 21** (owner; logged in `CHANGES_AFTER_FREEZE.md`)

## Checks done (5 Oct)

- Every Week 20 phase run end to end at small scale (200 hosts, 40 days); records validate against vmmbench/1.
- The Week 19 scripts run on the dry-run data; Table 3 compiles from `confirmatory.json` with no hand edits.
- `tests/v2` passes, including new tests for Morris (it ranks a known function correctly) and for the cost-model-error knob (it changes realised cost but not the policies' estimates).

## Compute (estimates on 8 cores, 2,000 hosts)

| Stage | Estimate |
| --- | --- |
| Week 18: P2 tuning (40 pairs) + A and E runs | about 4.5-5 h |
| Week 19: P2 tuning (24 pairs) + B, C and D runs | about 3 h |
| Week 20: ablations, retuning and robustness, Morris, failure runs | about 4 h |
