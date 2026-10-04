# Log

Sunday ritual (15 minutes): update this log, tick the week's "done when", log any cut as an ADR, re-read the next gate's criteria, update `CAPACITY.md` for the coming month, write Monday's first task. Newest week first. Hours are yours to fill; nothing here is estimated.

## Week 9 (30 Nov-6 Dec 2026)
- decision (4 Oct 2026): **skipped.** The citable v1 report is optional in the plan, and no application needs it before the v2 paper exists. The week's hours move to Week 10 (simulator spec). If it is revived later, it needs a dated correction section: the report presents the -3.1% at rho = 0 as a real result, and Week 3 showed it is mostly an accounting artifact (`v1_anomaly.md`)

## Weeks 7-8 (16-29 Nov 2026)
- started 4 Oct, ahead of the calendar, in parallel with the Week 4 ingest; entries completed when the runs finish

## Weeks 4-6 (26 Oct-15 Nov 2026)
- planned hours: 12 + 5 + 5   actual hours: __
- done (4 Oct, ahead of the weeks):
  - Backblaze: all 45 archives (35.1 GB) to Parquet with row counts checked and checksums recorded; quality report; AFR per model and year; life table; delayed-entry Kaplan-Meier; label spec
  - Week 6: trace chosen (Google 2019, free Parquet download), criticality mapping, rho definition, data sources; reading notes for Xu 2018 and Tirmazi 2020
- slipped (and why): the Botezatu 2016 note (closed access; yours, through the library)
- decisions made:
  - G1 combines cells by majority, with no majority meaning B (`PROTOCOL.md` v0.1, confirmed)
  - the G1 axis is made precise, pH = 0.30 on v1's Spearman axis = 0.375 on the latent axis (v0.2, written before any estimate; to confirm)
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
