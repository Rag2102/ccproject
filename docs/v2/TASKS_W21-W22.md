# Tasks, Weeks 21-22

From the v5 week cards for W21 and W22 (plan page 21). Prepared on 5 Oct 2026, ahead of the calendar (W21 starts 22 Feb 2027). `[x]` = done and checked; `[~]` = built, waiting for the runs or for you; `[ ]` = not done.

## Week 21 (22-28 Feb): adaptive regime, seed replication, second source; Gate G3; results freeze

- [~] **P6 on regime D** (`scripts/v2/33_adaptive.py` → `results/summary/adaptive_D.json`, F8 `results/figures/v2_F8_adaptive.pdf`):
  - regret against the better fixed policy in hindsight;
  - share of its benefit captured;
  - Δ vs P2;
  - switches, and the detection delay after the mid-run shift;
  - the H4 targets (≥ 90% captured; never more than 1% worse than P2), per seed.
  - Runs on the D cells of the frozen matrix.
- [~] **Seed replication** (`scripts/v2/run_w21.sh`, included in `run_overnight.sh`):
  - the confirmatory cells (A3, A5, B1, B2, C × 1%, 2%; P2, P4-P6 plus P0) on seeds 1001-1030;
  - → `results/raw/<group>/replication/`, `results/summary/confirmatory_replication.json`.
  - Reported as seed replication: it tests luck, not misspecification.
- [~] **Second placement source: decision for you.**
  - Alibaba 2018 was chosen.
  - Its machine metadata (checksums verified) has no risk signal: 4,034 machines, all "USING" for the whole trace, no attribute changes, undocumented periodic snapshots.
  - The 20 GB batch file was not downloaded.
  - Options: a second Google 2019 cell; a weaker Alibaba proxy (machine utilisation outliers, which would be a new, unvalidated proxy); or cut by ADR (G3 at most Medium).
- [x] **Small reproduction:**
  - `make reproduce-small` regenerates reduced F4, F5, F8 and Table 3 with every summary in **3.6 minutes** on this laptop (target: under an hour).
  - It found and fixed a B2 world-generation bug at small scale (logged; the frozen matrix is unaffected).
- [~] **Gate G3:** `docs/v2/G3_decision.md` is a template: the rule copied from the protocol and each input tied to its file. Theory-vs-MC is already filled (3,024 / 3,024).
- [ ] Freeze results: tag `results-frozen` (yours, after G3)
- [x] **Venues** (`VENUES.md`):
  - SoCC checked on the official page: two rounds (Feb and Jul).
  - Format `\documentclass[sigconf, review, anonymous]{acmart}`, 9 pt, 12 pages plus references, dual-anonymous.
  - A round-1 rejection can't be resubmitted in round 2.
  - No SoCC 2027 CFP yet. DSN not verified (no official page found).

## Week 22 (1-7 Mar): paper draft v1 and the Console skeleton

- [~] **Template and build:**
  - `paper/main.tex` (SoCC format) with all sections;
  - `make paper` runs latexmk.
  - Not compiled here yet: LaTeX is not installed (BasicTeX, yours to install; commands in `paper/README.md`).
- [x] **numbers.tex** (`scripts/v2/40_numbers.py` → `paper/numbers.tex`):
  - 143 macros, all read from files; the 122 results macros print "??" until the runs exist, and `--strict` fails while any remain.
  - Test `tests/v2/test_paper_numbers.py` fails if the paper uses an undefined macro.
- [ ] **Write:** evaluation → approach and theory → problem → simulator; intro and abstract last.
  - The Evaluation skeleton exists. The Approach, Problem, Simulator and Datasets drafts exist from Weeks 11-17.
  - Results prose waits for the frozen numbers.
- [x] **Claims ledger** (`docs/v2/CLAIMS_LEDGER.md`): 13 rows, each with its evidence, interval, family and caveat; the result rows are marked open.
- [x] **Figures:**
  - `scripts/v2/figstyle.py` is used by every figure script: Okabe-Ito palette with one colour per policy, ≥ 8 pt, vector PDF with embedded fonts.
  - `make figures` rebuilds everything from `results/`.
- [x] **Console skeleton** (static, no npm, owner):
  - `console/index.html` with S1 Crossover Explorer, provenance badges, the measured ρ and the family table;
  - data from `scripts/v2/41_console_data.py` (`make console`);
  - a banner whenever the data is not the frozen summary.
