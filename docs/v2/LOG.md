# Log

Sunday ritual (15 minutes): update this log, tick the week's "done when", log any cut as an ADR, re-read the next gate's criteria, update `CAPACITY.md` for the coming month, write Monday's first task. Newest week first. Hours are yours to fill; nothing here is estimated.

## Weeks 23-28 (8 Mar-18 Apr 2027), prepared 5 Oct 2026
- planned hours: 14 + 12 + 12 + 10 + 7 + 7   actual hours: __
- done:
  - W23: complete draft (intro, background, related work, discussion with every assumed element, abstract, conclusion; notation and numbers passes).
  - W24: three mock reviews with a rebuttal table; Dockerfile and clean-container check, which found a real bug (git dependency, fixed); citations checked.
  - W25: artifact (Apache-2.0, CITATION.cff, fetch_data.sh with checksums, ARTIFACT.md, make reproduce/release); SoCC rules; Console S1-S4 with a double-blind build.
  - W26: submission pack draft and next-cycle plan.
  - W27-28 ready-now parts: feedback.csv, weakest-claim note, ADR-009, number-diff script, venue check.
- evaluation runs:
  - Week 18 running (started 02:56; about 95 min lost to sleep).
  - Weeks 19-21 and the second source taken off the queue at the owner's request; `scripts/v2/run_rest.sh` runs them.
- second source: cell f τ-b −0.004 (latent −0.006), would-be class C0, agrees with G1.
- found and fixed before any result was read (all in CHANGES_AFTER_FREEZE.md):
  - group S stats crash;
  - Table 3 missing the P0/P3 columns ADR-005 required;
  - git needed in a clean build.
- slipped (and why): everything that reads results (Evaluation prose, G3, claims ledger, RETRO) waits for the runs; PDF and page check wait for LaTeX.
- next: Week 18 analysis (A/E only, protocol order) as soon as it collects.

## Weeks 21-22 (22 Feb-7 Mar 2027)
- planned hours: 12 + 14   actual hours: __
- done (5 Oct, ahead of the weeks):
  - Week 21: the regime-D adaptive analysis and F8; the seed-replication launcher; `make reproduce-small` (3.6 min); the G3 template; SoCC verified on the official page.
  - Week 22: `paper/main.tex` (SoCC format); `numbers.tex` (143 macros) with a missing-macro test; the claims ledger; Okabe-Ito figure style; the static Console skeleton.
  - Bug fixed: B2 world generation at small scale; the frozen matrix is unaffected (logged).
- slipped (and why):
  - every result-dependent item (G3 verdict, results freeze, results prose) waits for the overnight runs;
  - the paper is not compiled yet (BasicTeX, yours to install);
  - the second placement source waits for a decision.
- decisions made: Alibaba 2018 as the second source (owner), then found unusable (no machine-risk signal); BasicTeX; a static Console with no npm.
- risks changed: R-new, second source. Alibaba 2018 has no failure signal; without a second source G3 cannot be Strong.
- next task: run `scripts/v2/run_overnight.sh`; decide the second source

## Weeks 17-20 (25 Jan-21 Feb 2027)
- planned hours: 12 × 4   actual hours: __
- done (4-5 Oct, ahead of the weeks):
  - Week 17:
    - THEORY.md (T1-T4; T4 partly false as stated), with a Monte Carlo check at 3,024 points, all in tolerance;
    - the break-even surface, and the v1 anomaly closed;
    - PROTOCOL v1.0 frozen with the matrix and scenario cards (tags `protocol-v1.0`, `v2.0-rc1`, `v2.0-rc2`);
    - the runner, statistics and F4 scripts, and a full dry run (528 of 528 cells);
    - the Approach section of the paper.
  - Earlier gaps closed: the benchmark schemas, regimes E and B2, and the tier-margin bug in the latent axis (regimes recalibrated).
  - Week 18: the launcher is ready. The P2 pre-filter bug was found in tuning and fixed before any evaluation run (CHANGES_AFTER_FREEZE).
  - Weeks 19-20: every script and runner built and smoke-tested (`TASKS_W19-W20.md`).
  - Site: redesign, a v2 research section, and the v2 ensemble in the live demo (`ui-redesign` branch).
- slipped (and why): the evaluation runs for Weeks 18-20. They take about 12 h of compute and run overnight on your machine (`scripts/v2/run_overnight.sh`).
- decisions made:
  - ADR-007: 2,000 hosts × 365 days, n = 30, with an SD-triggered extension;
  - ADR-008: the oracle for the main matrix;
  - natural cost spread in A;
  - P5 = faithful variant;
  - Week 20: P2 retuned per robustness setting, Morris in the repo, model-based worlds deferred past Week 21.
- found:
  - the advantage of cost-aware selection is driven by cost spread and is largest near ρ = 0 (theory);
  - flattening miscalibration is the dangerous direction for BAM;
  - v1's +0.2% under consistent accounting matches the closed form;
  - the deployed ensemble's test PR-AUC is 0.103 (one calibration on the mean), not Week 16's 0.131.
- risks changed: R3 (compute): the full matrix plus Week 20 is about 12 h on 8 cores, run overnight
- next task: run `scripts/v2/run_overnight.sh`; then statistics and the A and E paragraph before opening B and C

## Weeks 15-16 (11-24 Jan 2027)
- planned hours: 12 × 2   actual hours: __
- done (4 Oct, ahead of the weeks):
  - Week 15: P4 BAM-GB with BAM-time and BAM-cost variants, ablation flags, exact MILP check (mean gap 0.05% on simulator snapshots), identity test against P2; P5 Narya-inspired (simple and faithful) with `narya_differences.md`; behaviour smoke
  - Week 16: 20-model bootstrap ensemble; drift study 2019-2025 with rolling recalibration; policy cost of drift; P6 safe-adaptive guard; regime D; the pure-noise control
- slipped (and why): the risk-averse BAM variant and `TrainedModel` (wait for the model choice, ADR-006, running); drift-curve plot (comes with the paper figures); P6 smoke rerun with budget-tuned P2 (ADR-005, running)
- decisions made:
  - ADR-005: P2 is tuned to use the budget, as the protocol says (owner, 4 Oct). P2c is not a comparator; tables show P0 and P3 next to P2
  - ADR-006: the simulator's model is chosen by validation PR-AUC on raw scores, rule committed (0b05ff3) before the scores were computed
  - P6 falls back to P2, as pre-registered (owner, 4 Oct), although with budget-tuned P2 the fallback costs more than BAM and more than never migrating (P6 smoke rerun: regret 69-158%)
- found:
  - BAM as specified over-migrates: b = p·c·e − m ignores the value of waiting (decisions recur daily, most VMs leave before their host fails) and the destination's risk. Input for THEORY.md (Week 17)
  - P6's plug-in advantage uses BAM's own formula, so it is almost always positive; the calibration audit is the guard's real protection
  - the ensemble mean has test PR-AUC 0.131 against 0.074 for the single model (test period: informs, does not select)
  - calibration drifts: reliability slope 0.76-0.97 two years ahead; rolling recalibration recovers 0.90-0.99. Policy cost of drift about +1.0% (+0.5% recalibrated), within seed noise
- risks changed: R2 (no usable risk proxy) eased: the long-removal proxy gave a classifiable result, but it rests on only 79-166 long removals per cell; a second placement source is still needed before claim 1 is called falsified
- next task: write the model-choice result into ADR-006, then `TrainedModel`; the scale ADR (ADR-007) from pilot b

## Weeks 11-14 (14 Dec 2026-10 Jan 2027)
- planned hours: 12 × 4   actual hours: __
- done (4 Oct, ahead of the weeks): the simulator `vmsim/` end to end. Engine, migration, accounting, repairs, reference policies P0-P3, P7 and P8, P2 tuning, A regimes on the latent axis. G2 evidence: analytic, self-calibration, exact v1 regression, invariants, run time 2-5 s per run (target 10 s). Weeks 11-12 code was committed earlier the same day (see `TASKS_W11-W14.md`)
- slipped (and why): `TrainedModel` and worlds for eval seeds 1-30 (wait for the model choice); B1 pilot cell (running in pilot b)
- decisions made:
  - engine is day-stepped with exact times inside the day, and VMs shorter than a day are charged as transients (`SIM_SPEC.md` v0.2; needed for the run-time target)
  - budget filled in each policy's order, skipping VMs that no longer fit (the protocol's wording; the first version stopped at the first misfit and left about 10% unspent)
- decisions made later (4 Oct):
  - P2 tuning: the protocol's rule kept (ADR-005). The pilot showed it makes P2 worse than never migrating; P2c was proposed and not adopted
  - model choice by validation PR-AUC (ADR-006)
  - G2 accepted by owner and advisor; tag `sim-v2.0`
- found: the earlier "v1 accounting mode" idea is unnecessary. With static VMs, realised accounting is v1's accounting; what changes v1's result is VM churn
- risks changed: R3 (compute) eased: the full matrix is about 2 h on 8 cores at 5,000 hosts
- next task: read the pilot's SD of Delta and draft the scale ADR

## Week 9 (30 Nov-6 Dec 2026)
- decision (4 Oct 2026): **skipped.** The citable v1 report is optional in the plan, and no application needs it before the v2 paper exists. The week's hours move to Week 10 (simulator spec). If it is revived later, it needs a dated correction section: the report presents the -3.1% at rho = 0 as a real result, and Week 3 showed it is mostly an accounting artifact (`v1_anomaly.md`)

## Weeks 7-8 (16-29 Nov 2026)
- started 4 Oct, ahead of the calendar, in parallel with the Week 4 ingest
- Week 7 done (4 Oct): model v2 at H = 30, PR-AUC 0.074 against 0.0018 for v1's features on the same temporal split; ROC-AUC 0.884; ECE 2.3 × 10⁻⁴; leakage audit clean. The features step first ran out of memory (one pass over all 45 quarters) and now builds its drive table one quarter at a time
- found: logistic regression has a higher test PR-AUC than boosting (0.091 vs 0.074); rolling-origin PR-AUC drops to 0.044 in the last fold
- Week 8: all three cells downloaded; cell a's aggregation hung in DuckDB on an uncapped connection (fixed, restarted after the Week 14 pilot)
- Week 8 done (4 Oct): the stall was a DuckDB 1.5.6 bug (a CTE shared by a UNION ALL), fixed with a temp table and one query per window. **G1 = C0 in all three cells, signed off by owner and advisor on 4 Oct (`G1_decision.md`); tag `g1-c0`.** The sign of the correlation depends on the mapping and proxy; its size does not (|τ-b| ≤ 0.075)

## Weeks 4-6 (26 Oct-15 Nov 2026)
- planned hours: 12 + 5 + 5   actual hours: __
- done (4 Oct, ahead of the weeks):
  - Backblaze: all 45 archives (35.1 GB) to Parquet with row counts checked and checksums recorded; quality report; AFR per model and year; life table; delayed-entry Kaplan-Meier; label spec
  - Week 6: trace chosen (Google 2019, free Parquet download), criticality mapping, rho definition, data sources; reading notes for Xu 2018 and Tirmazi 2020
- slipped (and why): the Botezatu 2016 note (closed access; yours, through the library)
- decisions made:
  - G1 combines cells by majority, with no majority meaning B (`PROTOCOL.md` v0.1, confirmed)
  - the G1 axis is made precise, pH = 0.30 on v1's Spearman axis = 0.375 on the latent axis (v0.2, written before any estimate; confirmed)
  - cells a, b and h, chosen before any data by workload mix
- found:
  - v1's third-party table is Backblaze 2013-2017 restricted to drives of at least 1.5 TB; with that filter the rebuild gives 122,620 vs 122,619 drives and 6,907 vs 6,913 failures, and the per-model and per-age tables match within a few drives
  - v1's `age_days` is power-on hours at the last report / 24
  - one day file (2018-02-25.csv) has M/D/YY dates and CR line endings; the first ingest silently dropped it, and the fixed ingest (version 2) re-converted every archive
- risks changed: R8 (dataset terms) eased: Backblaze, Google 2019 (CC-BY 4.0) and Azure V1 terms read and recorded in `data_sources.md`. R2 (no usable risk proxy) stays open until the Week 8 run
- next task: Week 7 final run on 2023-2026 once the ingest finishes

## Week 3 (19-25 Oct 2026)
- planned hours: 12   actual hours: __
- done (4 Oct, ahead of the week): v1 re-run from the tag reproduces exactly; `scripts/v2/diag_v1_anomaly.py`; `v1_anomaly.md` with 8 verdicts; `PROTOCOL.md` v0 with gates and power plan; advisor email draft; tag `protocol-v0`
- slipped (and why): sending the advisor email (yours)
- decisions made (ADR ids): none; four deviations from the pre-written verdict rules are listed in `v1_anomaly.md` section 4
- risks changed: R7 (novelty thin) eased: the v1 loss is an accounting artifact, and under consistent accounting the theory's prediction (no loss) held on 10 of 10 synthetic seeds
- next week's first task: Week 4 task 1, record the Backblaze source (download needs your go-ahead: see the reply)

## Week 2 (12-18 Oct 2026)
- planned hours: 12   actual hours: __
- done: charter, falsification list, seven reading notes, `refs.bib` (17 papers + 8 sources, each checked), T5 draft, benchmark landscape: all drafted on 4 Oct, ahead of the week (see `TASKS_W1-W2.md`)
- slipped (and why): not done yet: your read-aloud pass on the charter; reading NENYA and Deoxys in full; confirming the OSDI wording of Narya numbers
- decisions made (ADR ids): none new
- risks changed: R7 (novelty judged thin): Elkan makes the rule non-novel and NENYA/Deoxys are closed-data cost-aware mitigation; the novelty claim is now limited to measurement, surface, guard and benchmark
- next week's first task: reproduce 442,701 vs 456,533 from the v1 tag (`scripts/11_headline_matched.py` already reproduces the matched row from the per-host file)

## Week 1 (5-11 Oct 2026)
- planned hours: 12   actual hours: __
- done: scaffold, v1 freeze (`v1_reference/`, 32 files, read-only), `uv.lock`, Makefile, lint job in CI, ADR-001 to ADR-004, VENUES seeded, plan PDFs saved, tag `v1.0-course` pushed, table defect found and fixed on the live demo (verified on the page)
- slipped (and why): not done yet: advisor email (draft in `advisor_email_draft.md`, owner sends), CAPACITY hours (owner), reply on the AWS support case (owner), confirmation that the three Terraform fixes reached `main`, a green CI run seen on GitHub
- decisions made (ADR ids): ADR-001 to ADR-004
- risks changed: R6 (AWS verification): ADR-001 keeps AWS off the critical path
- next week's first task: read the charter aloud and delete any sentence you cannot defend
