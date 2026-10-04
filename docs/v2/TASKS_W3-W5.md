# Tasks for Weeks 3-5 (19 Oct - 8 Nov 2026)

Taken from the v5 week cards for W3, W4 and W5 (plan pages 13-14), adjusted for what already exists in the repository. Hours per task are my estimates within each week's budget. `[ ]` = not done.

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
- [ ] `git worktree add ../ccproject-v1 v1.0-course`. Use a separate worktree because `06_simulation_evaluation.py` overwrites `simulation_headline_summary.csv` and the per-host file
- [ ] Run `scripts/06_simulation_evaluation.py` there; confirm 442,701 (threshold at matched budget, 5,522 migrations) vs 456,533 (cost-sensitive, 5,116 migrations)
- [ ] Diff the new per-host file against `v1_reference/data/simulation_results_per_host.csv`
- If it does not reproduce exactly, stop and debug: that is the first finding
- If blocked (v1 cannot be re-run): reproduce from the `v1_reference` CSVs (`scripts/11_headline_matched.py` already does this for the totals) and log the gap as ADR-005

### 2. Write H1-H8 (about 1.5 h)
- [ ] `docs/v2/v1_anomaly.md`, one section per hypothesis, each with the result that would confirm or reject it:
  - H1: host-level p is miscalibrated after placement
  - H2: urgency(TTF) misbehaves
  - H3: the budget is matched in count, not GB
  - H4: the 58% Unknown class flattens costs
  - H5: p is too noisy to rank by a product
  - H6: accounting is asymmetric
  - H7: the density denominator m is not the budgeted resource (GB)
  - H8: the baseline's within-host VM order

### 3. One diagnostic each (about 4 h)
- [ ] `scripts/v2/diag_v1_anomaly.py`:
  - H7: re-rank by b / w with w = GB, at the same GB budget
  - H8: re-run P1 with smallest-first, largest-first and random within-host order
  - H5: oracle p plus Gaussian noise of growing sigma until the order flips
  - H3 and H4 (to reach at least five verdicts): match the budget in GB; recompute with Unknown dropped or reweighted
- [ ] Verdict per hypothesis (confirmed / rejected / inconclusive) with its figure; export `results/summary/v1_anomaly.json` (result R13)

### 4. Protocol v0 (about 2 h)
- [ ] `PROTOCOL.md`. Section 1 is `docs/v2/FALSIFICATION.md`. Then:
  - policies P0-P8, with P4 = BAM-GB primary and BAM-time / BAM-cost as ablations
  - P2 = best of three within-host orders, tuned on seeds 101-110
  - regimes A1-A7, B1, B2, C, D, E; budgets 0.5 / 1 / 2 / 5%
  - metrics; materiality delta = 1%
  - the 30-comparison confirmatory family (Holm); everything else exploratory; negative results reported

### 5. Exhaustive gates (about 1.5 h)
- [ ] G1: classes A / B / C0 / C1 / D against pH = 0.30, precision rule (CI width > 0.30 means class B), "class is final"
- [ ] G2: five criteria (analytic checks, self-calibration, v1 regression within 1%, invariants and determinism, run time); G2-late runs to 10 Jan 2027
- [ ] G3: Strong / Medium / Weak. Strong needs the win criterion in a real-trace regime, theory that matches, seed replication and a second placement source that agree
- [ ] Paste the numeric criteria into the protocol. The meanings of classes A-D are defined in the attached v3 package (Part V), not in the pages read so far; look them up

### 6. Power plan (about 0.5 h)
- [ ] Insert the max-SD table: SD of the paired difference must be below 2.7% uncorrected / 1.6% Bonferroni at 30 seeds (3.5 / 2.1% at 50, 5.0 / 3.1% at 100)
- [ ] Rule: the Week 14 pilot chooses seeds, hosts and horizon; delta never moves
- [ ] Pre-specify the regression adjustment of the difference on realised failure count

### 7. Advisor check (about 0.5 h)
- [ ] Send the charter, anomaly note and protocol v0; ask "what would you attack first?"
- [ ] Tag `protocol-v0`

Deliverables: `v1_anomaly.md` with at least 5 verdicts; diagnostic script; `PROTOCOL.md` v0 tagged `protocol-v0`; gates with numbers.
Done when: you can state in two sentences why the threshold won at rho = 0, or list exactly which hypotheses remain open and the week each closes.

## Week 4 (26 Oct - 1 Nov): Backblaze ingest pipeline

About 12 h. Phase P1 starts.
Goal: a resumable, checksummed CSV-to-Parquet pipeline for every Backblaze quarter, with a quality report and the drive-to-group columns that justify drives-per-host d.

Before starting: DuckDB is not installed (`uv add duckdb pyarrow`). 220 GiB were free on this Mac on 4 Oct; the total size of the quarterly files is not yet measured (task 2).

### 1. Record the source (about 1 h)
- [ ] `docs/v2/data_sources.md`: download page, terms of use, access date, file list, sizes, SHA-256 per file
- The terms were read on 4 Oct (in `docs/v2/benchmark_landscape.md`): cite Backblaze; you are responsible for your use; derivative works may be sold, the data itself may not. Copy them across and re-check the page on the day you download

### 2. Plan the disk (about 0.5 h)
- [ ] `df -h`; per quarter: download, convert to Parquet, verify row counts, delete the raw CSV, keep the checksum
- [ ] Keep raw copies on an external drive or a DVC remote if you want to re-derive

### 3. Ingest script (about 4 h)
- [ ] `scripts/v2/10_backblaze_ingest.py` with DuckDB: `DESCRIBE` each quarter first
- [ ] `read_csv_auto(..., union_by_name=true, sample_size=-1)`; force DOUBLE on SMART columns
- [ ] Keep date, serial_number, model, capacity_bytes, failure, SMART 5 / 9 / 12 / 187 / 188 / 190 / 194 / 197 / 198 / 199, and the datacenter / cluster / pod / vault columns where present

### 4. Resumable by design (about 1.5 h)
- [ ] Skip a quarter whose Parquet and checksum already exist
- [ ] Write `data/v2/backblaze/manifest.csv` (quarter, rows, failures, sha256, schema hash); keep the Parquet files out of Git
- [ ] Start the full run in the background with `nohup ... --all`

### 5. Quality report (about 2 h)
- [ ] `docs/v2/data_quality_report.md`: duplicate (date, serial) rows; serials reused across models; drives reporting after failure = 1; non-monotone power-on hours; null rate per SMART column per model; date gaps

### 6. Group columns (about 1.5 h)
- [ ] Where pod or vault IDs exist, histogram the drives per group: the evidence for the d in {1, 4, 12} sweep and a partial real drive-to-group mapping

### 7. Sanity against v1 (about 1.5 h)
- [ ] The 2013-2017 slice must reproduce v1's counts within rounding: about 122.6 K drives and about 6.9 K failures (v1: 122,618 and 6,912)
- v1 used a third-party per-drive summary, so a small gap may come from its definitions; record any gap rather than tuning it away

Deliverables: ingest script, manifest, `data_sources.md`, quality report, Parquet for every finished quarter.
Done when: the 2013-2017 slice matches v1's drive and failure counts within rounding, and the manifest lists every finished quarter with a checksum.
If blocked: if the disk is short, ingest 2013-2019 now and the rest in Week 5; the model needs at most three recent years for the temporal split.

## Week 5 (2-8 Nov): finish the ingest; AFR, life tables, label spec

About 5 h. Light week.
Goal: population-level failure behaviour is understood and the labels are specified before any model is trained.

### 1. Babysit the ingest (about 0.5 h)
- [ ] Re-run only the failed quarters; log malformed ones in the quality report

### 2. AFR table and drift (about 1 h)
- [ ] Per model and year: drive-days, failures, AFR = failures / (drive-days / 365), saved to `results/v2/afr_by_model_year.csv`
- [ ] Plot fleet AFR per year: it sets the failure-rate scale for regimes A5 and D

### 3. Life table and Kaplan-Meier (about 0.5 h)
- [ ] One row per drive: first_seen, last_seen, failed, model, capacity, age
- [ ] Kaplan-Meier curves for the ten largest models as a sanity figure (v1's hand-written estimator in `scripts/09_kaplan_meier_baseline.py` can be reused)

### 4. Label specification (about 0.5 h, text only)
- [ ] H in {7, 14, 30} days; a drive-day is positive if the drive fails within H days; the last H days of a non-failed drive are censored and excluded. Write it; no code

### 5. Reading (about 3 h)
- [ ] Xu et al., ATC 2018: pages 1-6 were read on 4 Oct; finish it and write `reading/xu2018cdef.md`. It warns that random or cross-validation splits overstate accuracy, the same split v1 used
- [ ] Botezatu et al., KDD 2016: write the note, check its citation on the publisher page, then add it to `paper/refs.bib`

Deliverables: AFR table and drift plot, life table, Kaplan-Meier figure, label specification, two reading notes.
Done when: AFR for the overlapping years matches v1. v1 has no per-year AFR table, only `backblaze_failure_rate_by_model.csv` and `_by_age.csv` for 2013-2017, so compare against those.
