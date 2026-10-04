# Log

Sunday ritual (15 minutes): update this log, tick the week's "done when", log any cut as an ADR, re-read the next gate's criteria, update `CAPACITY.md` for the coming month, write Monday's first task. Newest week first. Hours are yours to fill; nothing here is estimated.

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
