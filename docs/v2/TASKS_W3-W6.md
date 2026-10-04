# Tasks for Weeks 3-6 (19 Oct - 15 Nov 2026)

Taken from the v5 week cards for W3, W4, W5 and W6 (plan pages 13-17; Week 6 added on 4 Oct), adjusted for what already exists in the repository. Hours per task are my estimates within each week's budget. `[ ]` = not done.

## Carried over from Weeks 1-2 (yours, do first)

- [ ] Advisor email sent (draft: `docs/v2/advisor_email_draft.md`)
- [ ] Real hours in `docs/v2/CAPACITY.md`; reply on the AWS support case
- [ ] Green CI run seen on GitHub for `v2-research`
- [ ] Charter read aloud; lines marked [check] decided
- [ ] Narya explained without notes; NENYA and Deoxys read in full (T5 rows are abstract-only)

## Week 3 (19-25 Oct): explain the v1 anomaly; protocol v0; exhaustive gates

About 12 h. Deep-work week. Milestone M1.
Goal: a written diagnosis of the -3.1% at rho = 0, and a protocol that fixes every decision rule before any new data is seen.

### 1. Reproduce the number from the tag (about 1.5 h)
- [x] `git worktree add ../ccproject-v1 v1.0-course`. Use a separate worktree because `06_simulation_evaluation.py` overwrites `simulation_headline_summary.csv` and the per-host file
- [x] Run `scripts/06_simulation_evaluation.py` there; confirm 442,701 (threshold at matched budget, 5,522 migrations) vs 456,533 (cost-sensitive, 5,116 migrations)
- [x] Diff the new per-host file against `v1_reference/data/simulation_results_per_host.csv`
- If it does not reproduce exactly, stop and debug: that is the first finding
- If blocked (v1 cannot be re-run): reproduce from the `v1_reference` CSVs (`scripts/11_headline_matched.py` already does this for the totals) and log the gap as ADR-005

### 2. Write H1-H8 (about 1.5 h)
- [x] `docs/v2/v1_anomaly.md`, one section per hypothesis, each with the result that would confirm or reject it:
  - H1: host-level p is miscalibrated after placement
  - H2: urgency(TTF) misbehaves
  - H3: the budget is matched in count, not GB
  - H4: the 58% Unknown class flattens costs
  - H5: p is too noisy to rank by a product
  - H6: accounting is asymmetric
  - H7: the density denominator m is not the budgeted resource (GB)
  - H8: the baseline's within-host VM order

### 3. One diagnostic each (about 4 h)
- [x] `scripts/v2/diag_v1_anomaly.py`:
  - H7: re-rank by b / w with w = GB, at the same GB budget
  - H8: re-run P1 with smallest-first, largest-first and random within-host order
  - H5: oracle p plus Gaussian noise of growing sigma until the order flips
  - H3 and H4 (to reach at least five verdicts): match the budget in GB; recompute with Unknown dropped or reweighted
- [x] Verdict per hypothesis (confirmed / rejected / inconclusive) with its figure; export `results/summary/v1_anomaly.json` (result R13)

### 4. Protocol v0 (about 2 h)
- [x] `PROTOCOL.md`. Section 1 is `docs/v2/FALSIFICATION.md`. Then:
  - policies P0-P8, with P4 = BAM-GB primary and BAM-time / BAM-cost as ablations
  - P2 = best of three within-host orders, tuned on seeds 101-110
  - regimes A1-A7, B1, B2, C, D, E; budgets 0.5 / 1 / 2 / 5%
  - metrics; materiality delta = 1%
  - the 30-comparison confirmatory family (Holm); everything else exploratory; negative results reported

### 5. Exhaustive gates (about 1.5 h)
- [x] G1: classes A / B / C0 / C1 / D against pH = 0.30, precision rule (CI width > 0.30 means class B), "class is final"
- [x] G2: five criteria (analytic checks, self-calibration, v1 regression within 1%, invariants and determinism, run time); G2-late runs to 10 Jan 2027
- [x] G3: Strong / Medium / Weak. Strong needs the win criterion in a real-trace regime, theory that matches, seed replication and a second placement source that agree
- [x] Paste the numeric criteria into the protocol. The meanings of classes A-D are defined in the attached v3 package (Part V), not in the pages read so far; look them up

### 6. Power plan (about 0.5 h)
- [x] Insert the max-SD table: SD of the paired difference must be below 2.7% uncorrected / 1.6% Bonferroni at 30 seeds (3.5 / 2.1% at 50, 5.0 / 3.1% at 100)
- [x] Rule: the Week 14 pilot chooses seeds, hosts and horizon; delta never moves
- [x] Pre-specify the regression adjustment of the difference on realised failure count

### 7. Advisor check (about 0.5 h)
- [~] Send the charter, anomaly note and protocol v0; ask "what would you attack first?" (draft: `docs/v2/advisor_email_w3_draft.md`; yours to send)
- [x] Tag `protocol-v0`

Status (4 Oct): done except sending the email. Eight verdicts (H6 confirmed: v1's accounting credited migrations for failures months later; H2, H4, H5, H7, H8 rejected; H1, H3 inconclusive). `docs/v2/PROTOCOL.md` is `docs/v2/`, not the repository root, following the v5 layout.

Deliverables: `v1_anomaly.md` with at least 5 verdicts; diagnostic script; `PROTOCOL.md` v0 tagged `protocol-v0`; gates with numbers.
Done when: you can state in two sentences why the threshold won at rho = 0, or list exactly which hypotheses remain open and the week each closes.

## Week 4 (26 Oct - 1 Nov): Backblaze ingest pipeline

About 12 h. Phase P1 starts.
Goal: a resumable, checksummed CSV-to-Parquet pipeline for every Backblaze quarter, with a quality report and the drive-to-group columns that justify drives-per-host d.

Started 4 Oct, ahead of the calendar. DuckDB 1.5.6 and pyarrow added. The 45 archives are 35.1 GB compressed; 220 GiB were free.

### 1. Record the source (about 1 h)
- [x] `docs/v2/data_sources.md`: download page, terms of use, access date, file list, sizes, SHA-256 per file (`results/v2/backblaze_archives.csv`)
- The terms were read on 4 Oct (in `docs/v2/benchmark_landscape.md`): cite Backblaze; you are responsible for your use; derivative works may be sold, the data itself may not. Copy them across and re-check the page on the day you download

### 2. Plan the disk (about 0.5 h)
- [x] `df -h`; per quarter: download, convert to Parquet, verify row counts, delete the raw CSV, keep the checksum
- [x] Raw ZIPs kept in `data/v2/backblaze/raw/` (35 GB) so Parquet can be rebuilt without a new download; delete them if the disk gets short

### 3. Ingest script (about 4 h)
- [x] `scripts/v2/10_backblaze_ingest.py` with DuckDB: `DESCRIBE` each quarter first
- [x] Read every column as text (`all_varchar`, `union_by_name`), then cast: SMART to DOUBLE, never inferred
- [x] Keep date, serial_number, model, capacity_bytes, failure, SMART 5 / 9 / 12 / 187 / 188 / 190 / 194 / 197 / 198 / 199, and the datacenter / cluster / pod / vault columns where present

### 4. Resumable by design (about 1.5 h)
- [x] Skip a quarter whose Parquet and checksum already exist (and that the current code version converted)
- [x] Write `data/v2/backblaze/manifest.csv` (quarter, rows, failures, sha256, schema hash); keep the Parquet files out of Git
- [x] Start the full run in the background with `nohup ... --all`

### 5. Quality report (about 2 h)
- [x] `docs/v2/data_quality_report.md` (generated by `scripts/v2/10a_backblaze_summaries.py`): duplicate (date, serial) rows; serials reused across models; drives reporting after failure = 1; non-monotone power-on hours; null rate per SMART column per model; date gaps

### 6. Group columns (about 1.5 h)
- [x] Where pod or vault IDs exist (from 2023 Q2), histogram the drives per group: the evidence for the d in {1, 4, 12} sweep and a partial real drive-to-group mapping

### 7. Sanity against v1 (about 1.5 h)
- [x] The 2013-2017 slice must reproduce v1's counts within rounding: about 122.6 K drives and about 6.9 K failures (v1: 122,618 and 6,912)
- v1 used a third-party per-drive summary, so a small gap may come from its definitions; record any gap rather than tuning it away

Deliverables: ingest script, manifest, `data_sources.md`, quality report, Parquet for every finished quarter.
Done when: the 2013-2017 slice matches v1's drive and failure counts within rounding, and the manifest lists every finished quarter with a checksum.
If blocked: if the disk is short, ingest 2013-2019 now and the rest in Week 5; the model needs at most three recent years for the temporal split.

## Week 5 (2-8 Nov): finish the ingest; AFR, life tables, label spec

About 5 h. Light week.
Goal: population-level failure behaviour is understood and the labels are specified before any model is trained.

### 1. Babysit the ingest (about 0.5 h)
- [x] Re-run only the failed quarters; log malformed ones in the quality report (2018-02-25.csv: M/D/YY dates and CR line endings; fixed in the ingest, version 2)

### 2. AFR table and drift (about 1 h)
- [x] Per model and year: drive-days, failures, AFR = failures / (drive-days / 365), saved to `results/v2/afr_by_model_year.csv`
- [x] Plot fleet AFR per year: it sets the failure-rate scale for regimes A5 and D

### 3. Life table and Kaplan-Meier (about 0.5 h)
- [x] One row per drive: first_seen, last_seen, failed, model, capacity, age
- [x] Kaplan-Meier curves for the ten largest models as a sanity figure. New estimator with delayed entry: v1's in `scripts/09_kaplan_meier_baseline.py` starts every drive at age 0, but Backblaze drives enter the data part-way through their lives

### 4. Label specification (about 0.5 h, text only)
- [x] H in {7, 14, 30} days; a drive-day is positive if the drive fails within H days; the last H days of a non-failed drive are censored and excluded. Written: `docs/v2/label_spec.md`

### 5. Reading (about 3 h)
- [x] Xu et al., ATC 2018: read in full; `reading/xu2018cdef.md`. It warns that random or cross-validation splits overstate accuracy, the same split v1 used
- [~] Botezatu et al., KDD 2016: citation verified against the DOI's Crossref record and added to `paper/refs.bib`. The paper is closed access, so the note (`reading/botezatu2016.md`) is an empty template: get the PDF through your library and fill it in

Deliverables: AFR table and drift plot, life table, Kaplan-Meier figure, label specification, two reading notes.
Done when: AFR for the overlapping years matches v1. v1 has no per-year AFR table, only `backblaze_failure_rate_by_model.csv` and `_by_age.csv` for 2013-2017, so compare against those.

## Week 6 (9-15 Nov): pick the placement trace; define empirical rho

About 5 h. Light week. Done on 4 Oct, ahead of the calendar; nothing was downloaded from the trace.

- [x] Pick the trace and check access. Google 2019 is the choice.
  - BigQuery bills scans to your own project.
  - But the same tables are in public buckets as Parquet: 21 GB of `instance_events` for cell a, 176 GB for all 8 cells; `instance_usage` (3.4 TB) is not needed.
  - So Week 8 downloads one cell at a time with no BigQuery cost (needs your go-ahead with the size, like Backblaze).
  - Alternative: Alibaba 2018.
- [x] Read the trace paper and schema: `reading/tirmazi2020borg.md`; the v3 documentation and the format file give tiers, event codes, alloc sets and dedicated machines. DOI added to `paper/refs.bib`
- [x] `docs/v2/criticality_mapping.md`: M1 (priority tier, primary), M2 (scheduling class), M3 (strict joint); tasks only, dedicated machines excluded
- [x] `docs/v2/rho_definition.md`: placements, 7-day windows, risk proxies (platform long-removal rate primary), Kendall tau-b and tie-corrected Spearman, cluster bootstrap over machines, mapping to rho_L, threats. G1 combines cells by majority: confirmed and added to `PROTOCOL.md` section 7 (v0.1)
- [x] `data_sources.md` entries for the Google trace, Azure V1 (CC-BY-4.0 and MIT), LANL, and Alibaba as the fallback
- [x] Reading: Resource Central was done in Week 2 (`reading/resource_central2017.md`, pages 1-8 of 15)

Done when: a collaborator could compute rho from the trace by following the note alone. Check this by reading `rho_definition.md` as if you had never seen the project.
