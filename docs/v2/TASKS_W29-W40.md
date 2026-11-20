# Tasks, Weeks 29-40 (Phase 6: strengthen, polish, submit)

From the v5 week cards for W29-W40 (plan pages 23-26). Prepared on 26 Oct 2026, ahead of the calendar (W29 starts 19 Apr 2027), after the owner accepted ADR-009 and asked for everything that does not wait on results, people or the venue, **except Weeks 35 and 38** (owner: leave them). `[x]` = done and checked; `[~]` = built, waiting on runs or inputs; `[ ]` = not started; *yours* = owner-only.

## W29: strengthen the weakest claim I, data
- [x] ADR-009 accepted (owner, 26 Oct). The second trace path is already done (Week 21, cell f).
- [~] **Cost-range path.** Rule for low/high settings fixed in `configs/v2/cost_range.yaml` before any rerun. Clark et al. 2005 extracted (sections 6.2-6.5, Figures 8-12). **Five sources pending**: their text has to be fetched first (download approval). The settings derive automatically once four sources are in (`38_cost_range.py`). Voorsluys et al.: arXiv v2 is withdrawn; v1 is still served.
- [ ] Azure packing trace (optional): not planned.

## W30: strengthen the weakest claim II, runs
- [x] Scenario cards: `<regime>@G0-low/high` (`vmsim/scenarios.py`), cards marked migration DERIVED.
- [x] Dev seeds first: `39_dev_precheck.py` (invariants, utilisation, failures per run; dev seeds 101-110 only).
- [x] Run (2 Nov 2026, `RESULTS_COSTRANGE.md`): `run_w30.sh` (derive, pre-check, tune, run B1/B2/C at both ends, P0 P2 P4 P6, 1% and 2%, seeds 1-30, stats, vs P0, Table 3). About 2 h. Tested end to end at small scale with placeholder settings. Waits for the cost range and for the device.
- [x] Figures and tables: Table 3 gains exploratory rows (second source, cost range); `34_vs_p0.py --subdir`.

## W31: strengthen III, integrate; Console S5
- [ ] Re-assess G3: after the B/C results (`run_rest.sh`) and the cost range.
- [x] Ledger: C9 (avoidance, exploratory) added; C8's reason corrected; C5 built.
- [x] **Console S5 Paired Seeds**: the 30 comparisons, every seed a dot, Holm and win/SD-rule checklist, P0 view. JSON instead of DuckDB-wasm (`console/README.md`).

## W32: rewrite abstract and introduction
- [ ] Shape check, abstract, introduction order: after G3.
- [x] Contribution map: `48_contribution_map.py` (4 of 4 bullets have a ledger claim and a reference).
- [x] Positioning sentence: one candidate per G3 shape, plus the first-page checklist (`POSITIONING.md`).
- [ ] Cold read: *yours*.

## W33: rewrite evaluation and polish figures
- [ ] One subsection per RQ: after the runs.
- [x] Figures: per-policy markers and line styles; `44_grayscale_check.py` (14 close colour pairs, all separated); F4 has per-seed dots; F4b draws avoidance.
- [x] Appendix: pilot and scale, P2 order, P5 vs Narya, robustness grid stub (`appendix.tex`, macros only).
- [x] **Reporting audit**: `43_report_audit.py` (0 fail, 0 warn, 5 pending on B). It found the evaluation text quoting savings without intervals, and the refuted "option to wait" explanation for P5: both fixed.

## W34: related work; Console S6 and polish
- [ ] Literature sweep: closer to submission (the last 12 months before it).
- [x] **Console S6 Figures** (`results/figures/catalogue.yaml`).
- [~] Polish: light theme and toggle, reduced motion, 360 px (checked). axe, Playwright and Lighthouse need packages downloaded: not run.

## W35: artifact dry run on a different machine
- Left out (owner, 26 Oct).

## W36: anonymisation, statements, licences
- [~] Anonymised links: `make console-anon` exists; `45_anon_check.py` checks the paper, PDF, figure metadata and the anonymous Console, and lists the 21 tracked files the anonymous repository view must hide. Creating the anonymous_github view is *yours*.
- [x] Metadata check: pdfinfo, PNG text chunks, Office XML (exiftool used when installed).
- [x] Statements: ethics, data availability, artifact (`statements.tex`).
- [~] Licences: `LICENCE_REVIEW.md`. **Owner decision**: v1's third-party Backblaze summary has no licence file and feeds the frozen simulator. Re-read every dataset's terms in June 2027.

## W37: venue format and page cut
- [ ] CFP rules: no SoCC 2027 call yet (5 Oct). Re-check in the week.
- [~] Template: acmart sigconf, review, anonymous (in place). Font embedding is checked by `final_check.sh` once LaTeX is installed (*yours*: BasicTeX).
- [ ] Cut: after the rewrite.
- [x] References: `46_refs_check.py` (0 fail, 0 to do since 26 Oct: four DOIs and page ranges added from Crossref, two arXiv entries replaced by their NeurIPS 2025 versions, venue names made consistent, access years on datasets and software; papers with no DOI say how that was checked). Still yours: Gymnasium author order on the proceedings page; 4 uncited entries to cite or drop at the cut.

## W38: second mock review
- Left out (owner, 26 Oct).

## W39: final fixes
- [ ] Register the abstract: *yours*, if the venue asks.
- [x] **Final numbers check**: `final_check.sh` (clean clone; summaries and numbers rebuild byte for byte; passes now). Needed the cell Parquets committed, which `.gitignore` had blocked: fixed.
- [x] Supplementary: `47_supplementary.py` (anonymous Console, summaries, current figures, tables; strict anonymity check; 0.6 MB now).
- [x] Rebuttal prep: `REBUTTAL_FAQ.md` (ten questions; answers that wait on runs marked).

## W40: submit
- *Yours*: submit and tag `paper-a-submitted`, or retarget along the ladder (`VENUES.md`); preprint only if the venue and advisor allow; Phase 6 hours and retro in `LOG.md`.
