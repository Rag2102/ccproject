# Tasks for Weeks 1-2 (5-18 Oct 2026)

Six tasks, taken from the v5 week cards for W1 and W2 and adjusted for what the clone showed. Status as of 4 Oct 2026. `[x]` = done and checked; `[~]` = drafted or partly done, needs you; `[ ]` = not done. Most of Week 2 was drafted on 4 Oct, ahead of its dates; the Sunday tests still need you.

## Week 1 (5-11 Oct): finish the setup

### Task 1. Publish the setup
- [x] Commit the scaffold on `v2-research` in logical commits and push the branch (3 commits)
- [x] Create the annotated tag `v1.0-course` on `main` (729fb75) and push it
- [x] Install uv and create `uv.lock`
- [x] Add a ruff job to CI and the v2 badge to the README; `.python-version` set to 3.12
- [x] Check whether the three Terraform fixes reached `main`: `waf.tf`, `api_gateway.tf` and `config.js.tpl` were all last changed in commit 729fb75 (WAF and CloudFront), the head of `main`; the clone had no uncommitted changes. Still worth one look at `git diff` in your own terminal, since an uncommitted local copy is the only place a missing fix could be
- [x] ADR-004 (Python 3.12) accepted
- [ ] See a green CI run on GitHub (the repository is private; I could not open the Actions page)

Done when: `git status` is clean on `v2-research`, CI is green, the tag is visible on GitHub, and `make test` passes. Verified here: tag and branch are on the remote; `make test` passes (42); CI result not seen.

### Task 2. Fix the demo table and log the defect
- [x] Defect logged in `docs/v2/v1_final_state.md` (item 7)
- [x] Fixed on `main` in a77a5f6: new `scripts/11_headline_matched.py` recomputes three rows from the per-host file, Flask template and AWS frontend show matched and naive columns, note states 3.1% and 11.1%
- [x] Render redeployed (about 165 s) and the live page compared with the CSV: all 8 rows and the note match
- [~] The AWS static frontend shows "n/a" in the matched column until its API image is rebuilt and redeployed; that deployment was not touched

Done when: the live table's header matches its numbers and all columns tie back to `v1_reference/`. Verified on the live Render page.

### Task 3. Supervision and capacity
- [~] `docs/v2/advisor_email_draft.md` (from the plan's template); you add the name and course and send by Friday 9 Oct
- [ ] Fill real hours in `docs/v2/CAPACITY.md` for October and November (the file holds the plan's defaults)
- [ ] Reply on the existing AWS support case (ADR-001)
- [~] `docs/v2/LOG.md` has week entries; the hours and the Sunday ritual are yours

Done when: the email is sent, October is filled in, and Week 1 has a row in the log.

## Week 2 (12-18 Oct): charter, reading, positioning

### Task 4. Charter and falsification list
- [~] `docs/v2/CHARTER.md` drafted: thesis, RQ1-RQ4 and RQ6-RQ8 from the plan, C1-C5, non-goals with reasons. Marked items need your decision; the read-aloud pass is yours
- [~] `docs/v2/FALSIFICATION.md`: three claims with falsifiers; tolerances are fixed in Week 3 and Week 17

Done when: no sentence in the charter is one you cannot defend aloud, and each claim has a falsifier.

### Task 5. Read Narya and five more papers
- [x] `reading/levy2020narya.md` written from pages 1-16 of the report; the P5 spec differences are listed for Week 15
- [x] Notes for Clark 2005, Elkan 2001, Resource Central, Protean, Schroeder and Gibson (each names the pages read; two papers were read in part)
- [x] `reading/real_systems.md` from the OpenStack Watcher and KubeVirt documentation
- [ ] You, without notes: explain how Narya selects a mitigation (the Sunday test; the notes are not a substitute for reading it)

Done when: without notes you can explain how Narya selects a mitigation, and why VMMBench is not a Narya re-implementation.

### Task 6. Bibliography, positioning table, benchmark landscape
- [x] `paper/refs.bib`: 17 papers and 8 data or software sources, each checked on a publisher page or the paper's first page; Botezatu 2016 left out as unverified
- [~] `docs/v2/T5_positioning.md`: no empty cells; NENYA and Deoxys are abstract-only rows, to read in full
- [x] `docs/v2/benchmark_landscape.md`: no existing open benchmark for failure-mitigation decisions found in the sources checked, with the search log
- [ ] Sunday ritual in `docs/v2/LOG.md`

Done when: `refs.bib` has no unverified entry, T5 has no empty cell, and the landscape note either cites an existing benchmark or states why none was found.
