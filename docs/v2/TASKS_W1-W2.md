# Tasks for Weeks 1-2 (5-18 Oct 2026)

Six tasks, taken from the v5 week cards for W1 and W2 and adjusted for what the clone showed. Status is updated at the end of each task. `[x]` = done and checked, `[~]` = drafted or partly done, needs you, `[ ]` = not done.

## Week 1 (5-11 Oct): finish the setup

### Task 1. Publish the setup (about 3 h)
- [ ] Commit the scaffold on `v2-research` in logical commits and push the branch
- [ ] Create the annotated tag `v1.0-course` on `main` (729fb75) and push it
- [ ] Install uv and create `uv.lock`
- [ ] Add a ruff job and the v2 badge to CI; point `.python-version` at 3.12
- [ ] Check that the three Terraform fixes already reached `main`
- [ ] Confirm ADR-004 (Python 3.12)

Done when: `git status` is clean on `v2-research`, CI is green, the tag is visible on GitHub, and `make test` passes.

### Task 2. Fix the demo table and log the defect (about 1.5 h)
- [ ] Add the defect to the inconsistency list in `docs/v2/v1_final_state.md`
- [ ] After the tag exists, fix the findings table in `webapp/templates/index.html` and `cloud/frontend/` (naive threshold column relabelled, matched-budget column added from the per-host file)
- [ ] Correct the note under the table (about 3% vs matched, about 11% vs naive)
- [ ] Push `main`, let Render redeploy, compare the live page with the CSV

Done when: the live table's header matches its numbers and all three columns tie back to `v1_reference/`.

### Task 3. Supervision and capacity (about 2 h)
- [ ] Fill real hours in `docs/v2/CAPACITY.md` for October and November
- [ ] Send the advisor email by Friday 9 Oct
- [ ] Reply on the existing AWS support case (ADR-001)
- [ ] Sunday ritual in `docs/v2/LOG.md`

Done when: the email is sent, October is filled in, and Week 1 has a row in the log.

## Week 2 (12-18 Oct): charter, reading, positioning

### Task 4. Charter and falsification list (about 3.5 h)
- [ ] `docs/v2/CHARTER.md`: thesis, RQ1-RQ4 and RQ6-RQ8, contributions C1-C5, non-goals with reasons
- [ ] Read every sentence aloud; delete any you cannot defend
- [ ] `docs/v2/FALSIFICATION.md`: three claims, each with the result that would falsify it

Done when: no sentence in the charter is one you cannot defend aloud, and each claim has a falsifier.

### Task 5. Read Narya and five more papers (about 5 h)
- [ ] `reading/levy2020narya.md`: failure signals, actions, how a mitigation is selected, feedback, metrics, what is proprietary; correct the P5 spec if needed
- [ ] Notes with the template for Clark 2005, Elkan 2001, Resource Central, Protean, Schroeder and Gibson
- [ ] One evening on `openstack/watcher` and `kubevirt` migration policies (actions and cost fields)

Done when: without notes you can explain how Narya selects a mitigation, and why VMMBench is not a Narya re-implementation.

### Task 6. Bibliography, positioning table, benchmark landscape (about 3.5 h)
- [ ] `paper/refs.bib` with at least 15 entries, each checked on the publisher page
- [ ] `docs/v2/T5_positioning.md` with a "real-system analogue" column
- [ ] `docs/v2/benchmark_landscape.md`: Park, Gymnasium-style APIs, HELM, any existing open benchmark
- [ ] Sunday ritual in `docs/v2/LOG.md`

Done when: `refs.bib` has no unverified entry, T5 has no empty cell, and the landscape note either cites an existing benchmark or states why none was found.
