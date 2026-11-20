# Tasks, Weeks 23-26

From the v5 week cards for W23-W26 (plan page 24-25). Prepared on 5 Oct 2026, ahead of the calendar (W23 starts 8 Mar 2027), while the Week 18-21 evaluation runs were in progress. `[x]` = done and checked; `[~]` = built, waiting for the runs or for you; `[ ]` = not done.

## Week 23 (8-14 Mar): paper draft v2, complete

- [x] **Introduction** (`paper/sections/intro.tex`):
  - the problem, the gap, the prototype's finding and why it was wrong;
  - four contributions (C1-C4), each mapped to the claims ledger, and a roadmap.
  - Result sentences use only macros, so they read correctly whichever way the family comes out. One interpretive sentence per result waits for `results-frozen`.
- [x] **Background and motivation** (`background.tex`, new): Narya, what public traces say about the inputs, and the prototype's result and its diagnosis (`\label{sec:v1}`).
- [x] **Related work** (`related.tex`): four groups (failure prediction; mitigation systems; cost-sensitive learning and decision theory; simulators, traces and benchmarks), each ending with what it does not do.
- [x] **Discussion and threats to validity** (`discussion.tex`): internal, external and construct validity; Table `tab:assumed` names every synthetic or assumed element and the range it is varied over, in one place.
- [x] **Abstract** (184 words; every number a macro) and **conclusion** (`conclusion.tex`).
- [x] **Data and failure model** (`datasets.tex`): the failure-model paragraph (`sec:model`) and the measured correlation (`sec:rho`), which earlier sections already referenced.
- [x] **Notation pass:**
  - the notation table gains κ, ρ/ρ_L, τ_b, σ_p/σ_κ, q, γ and Δ;
  - the T3 formula's symbols are defined at first use;
  - σ_logκ is now σ_κ everywhere.
- [x] **Numbers pass:** every result in the text is a macro, including the prototype numbers, the G2 table and the cell f values. 222 macros, 176 placeholders until the runs.
- [~] **Cut to the page limit:**
  - about 6,000 words before the Evaluation prose, which estimates to 10-10.5 pages with figures;
  - the real check needs LaTeX (BasicTeX, yours).
- [~] **Evaluation prose:** waits for `results-frozen`. Protocol order: A/E first, then B/C.

## Week 24 (15-21 Mar): outside review and revision

- [~] **Send the draft** to the advisor and two readers (yours). Ready:
  - form `docs/v2/REVIEW/review_form.md`;
  - emails `REVIEW/reader_emails_draft.md`;
  - log `REVIEW/responses.md`.
  - The PDF needs LaTeX.
- [x] **Three adversarial reviews** (`REVIEW/mock_reviews.md`: R1 systems, R2 ML/statistics, R3 skeptic) and a rebuttal table.
  - Paper changes where the objection is right:
    - the oracle predictor is stated as an upper bound;
    - the adjustment is shown to be pre-treatment;
    - C0 holds on the direct reading;
    - fold variability is reported.
  - The biggest change came from R2.7/R3.2: **Table 3 now shows P0 and P3 beside P2, as ADR-005 required.** The frozen script had left them out; this was fixed before any result was read.
- [~] **Reproduce one table from scratch in a clean Docker container:**
  - `Dockerfile` (base pinned by digest);
  - `scripts/v2/docker_repro.sh`, which builds from `git archive HEAD` with Git LFS files as pointers, as in CI;
  - `scripts/v2/compare_tables.py`.
- [x] **Citations:** every entry was checked on 4 Oct against the publisher, proceedings, arXiv or Crossref. Dantzig (1957) was checked against Crossref today; uncited entries drop out of the bibliography automatically.
- [~] **Language pass:** after the Evaluation prose exists.
- [~] **Claims ledger update:** after results.

## Week 25 (22-28 Mar): artifact and preprint

- [x] **Artifact bundle:**
  - Docker:
    - `Dockerfile`;
    - `make reproduce-small` (about 4 min);
    - `make docker-repro`;
    - `make reproduce` (full, about 14 h).
  - `ARTIFACT.md`: what is where, hardware, times, expected outputs, determinism.
  - Data and checksums:
    - `scripts/v2/fetch_data.sh` (Backblaze 35.1 GB, Google cells 66 GB);
    - `data/CHECKSUMS.sha256` checked by `scripts/v2/verify_checksums.py` (48 / 48 match).
  - Licence and metadata:
    - `LICENSE` (Apache-2.0, your choice) and `NOTICE`;
    - `CITATION.cff`, `.zenodo.json`.
- [~] **Archive: Zenodo DOI and tag v2.0** (yours, after `results-frozen`; steps in `docs/v2/RELEASE.md`). `make release` runs the pre-release checks.
- [x] **Venue rules** (`VENUES.md`, SoCC checked on the official page).
  - SoCC allows preprints, **but the submission must use a system name different from any used in a preprint**. If a preprint says "VMMBench", the submission renames it.
  - Anonymised artifact link; 12 pages + unlimited references.
- [ ] **Preprint:** only after the advisor agrees (yours). The renaming rule above applies.
- [x] **Console S1-S4** (static, read-only; replaces the optional crossover-explorer page):
  - S2 Trace Lens: every G1 combination and the second source on the latent axis, with the C0 and break-even lines;
  - S3 Policy Lab: an illustrative p·c·e − m calculator plus the live-demo link;
  - S4 Run Matrix: cells present and card hashes;
  - double-blind build: `make console-anon`.

## Week 26 (29 Mar-4 Apr): buffer, submission pack, retrospective

- [~] **Submission checklist** (`docs/v2/SUBMISSION.md`, Appendix A.5): status per item, plus draft data, artifact and ethics statements.
- [x] **Next-cycle plan** (in `SUBMISSION.md`): ten weeks to SoCC 2027 round 2, unless G3 changes the venue.
- [~] **Venue choice:** from G3 and the 2027 call (not out yet).
- [~] **Retrospective** (`docs/v2/RETRO.md`): written once the runs finish. Actual hours are yours.
- [ ] **Backups** (yours): repo tag, Zenodo DOI, local and external copies of `results/`.
