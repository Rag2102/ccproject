# Tasks, Weeks 27-28 (Phase 6, polish and submit)

From the v5 week cards for W27 and W28 (plan page 23). Prepared on 5 Oct 2026, ahead of the calendar (W27 starts 5 Apr 2027). Only the parts that need neither the Week 19-21 results nor outside feedback are built. `[x]` = done and checked; `[~]` = started, waiting on something named; `[ ]` = not done.

## Week 27 (5-11 Apr): collect and triage all feedback

- [~] **Consolidate** (`docs/v2/feedback.csv`: id, source, section, claim affected, comment, severity, effort, decision, owner week, status, commit).
  - Seeded with the 18 objections from the three mock reviews: 10 closed with their commits, 8 open (3 must, 4 should, 1 could).
  - The advisor's and readers' comments join when they reply (yours to send; `REVIEW/reader_emails_draft.md`).
- [~] **Weakest claim** (`docs/v2/WEAKEST_CLAIM.md`): provisionally C3a, BAM vs P2 in B1/B2. It carries the most assumptions, uses the oracle, and is measured against a contested comparator. Re-check after the runs: widest simultaneous interval, largest Morris exposure.
- [x] **Strengthening experiment** (`DECISIONS/ADR-009-strengthening-experiment.md`, proposed; yours to accept). The second trace is already done (cell f, C0), so the choice is a published migration-cost range:
  - six sources, each checked to exist with title, venue and year, including a SoCC 2015 paper on live-migration performance models;
  - rerun B1, B2 and C at the range's ends, exploratory, about 2 h.
- [x] **Post-freeze labelling:** every change since the freeze is in `CHANGES_AFTER_FREEZE.md` (15 rows). ADR-009's work will be added when it runs.
- [x] **Venue check:** no SoCC 2027 call yet (acmsocc.org/2027 is 404). Inferred dates stand; recorded in `VENUES.md` with the date.

## Week 28 (12-18 Apr): fix the must-fix items

- [~] **Text and figures:** the 3 open must-fix items (R2.1, R3.2, R3.4) need the results. Each closes with a commit that names its feedback id.
- [ ] **Bugs:** none open. Found and fixed so far (logged): the second-source stats crash, the missing P0/P3 columns, and the git dependency in a clean container.
- [x] **Number diff** (`scripts/v2/42_numbers_diff.py`, test `tests/v2/test_numbers_diff.py`):
  - prints every macro that changed between two revisions, old → new and the difference;
  - reports placeholders filled, macros added and macros removed;
  - `--md` gives a table for the log.
- [~] **Rebuild from a clean checkout:** `make figures` runs from results; `make paper` needs LaTeX (BasicTeX, yours). `make docker-repro` (end of `run_rest.sh`) covers the clean-checkout half for the small figures.
