# Venues (seeded from v5 Part IV; every date is inferred until checked on the official page)

Last checked on an official page: 5 Oct 2026 (SoCC only; Week 21 task 7, done early). Record the check date in the last column when you do.

| Venue | Expected deadline | Status | Role | Checked on |
| --- | --- | --- | --- | --- |
| SoCC 2027 | about early July 2027, the second round (SoCC 2026: two rounds; round 1 abstracts 6 Feb, papers 13 Feb 2026; round 2 abstracts 7 Jul, papers 14 Jul 2026). No SoCC 2027 CFP yet | inferred from 2026 | Primary target for Paper A (Weeks 39-40 = round 2). Format: `\documentclass[sigconf, review, anonymous]{acmart}`, 9 pt, 12 pages plus references, dual-anonymous. A paper rejected in round 1 may not be resubmitted in round 2 | 5 Oct 2026 (acmsocc.org/2026/papers.html) |
| DSN 2028 | about Nov-Dec 2027 (DSN 2027 listed 25 Nov 2026) | inferred | Strong fit; Paper A retarget or Paper B rung | not verified 5 Oct 2026: no official DSN 2027 page found |
| ICPE 2028 | about mid-Jan 2028 (ICPE 2025 research deadline 15 Jan 2025) | inferred | Fallback; has artifact and data-challenge tracks | |
| IEEE CLOUD 2028 | about early Mar 2028 (CLOUD 2026: 8 Mar 2026) | inferred | Fallback rung | |
| NSDI 2028 spring / EuroSys 2028 spring | about late Apr / mid-May 2027 | inferred | Only if G3 is Strong and Phase 6 is compressed | |
| Journals (JoCC, IEEE TCC, TPDS, TSC, FGCS) | rolling | check scope | Paper B | |
| Benchmark / reproducibility venues | not checked | verify | Only if VMMBench attracts ML-policy entries | |

Rule: never submit overlapping work to two venues at the same time. A rejection is progress: revise within two weeks and move one rung.

## SoCC 2027 call: checked 5 Oct 2026 (Week 27, task 5)

`acmsocc.org/2027/` returns 404, and no 2027 call appears in search; SoCC 2026 was in Singapore with the two-round model. The inferred dates (round 2 about early July 2027) stand. Check again monthly: when the call appears, re-check every row below and shift Weeks 37-40 if the dates differ.

## Venue-rule checklist: SoCC (Week 25, checked 5 Oct 2026 on acmsocc.org/2026/papers.html)

The 2027 call is not out; these are SoCC 2026's rules. Re-check every row the day the 2027 call appears.

| Rule | SoCC 2026 says | What we do |
| --- | --- | --- |
| Format | `\documentclass[sigconf, review, anonymous]{acmart}`, 9 pt | `paper/main.tex` uses it |
| Length | Full research papers: 12 pages + unlimited references (short and vision: 6) | Target 11 pages + references; appendices count against the 12 unless the 2027 call says otherwise |
| Anonymity | Dual-anonymous | Author block "Anonymous"; no repository URL in the submission. Link the artifact through an anonymised mirror (for example anonymous.4open.science) built from the release tag; owner creates it |
| Preprints | Allowed (arXiv, technical reports, talks, social media), **but the submission must use an anonymised system or project name different from any used in such contexts** | If a preprint names the benchmark "VMMBench", the submission renames it (for example "the benchmark") and drops the repository name. Decide before posting |
| Round 1 / round 2 | A paper rejected in round 1 may not be resubmitted in round 2 | Submit in one round only; the plan targets round 2 |
| Artifact evaluation | Not stated on the page | Artifact ready regardless (`ARTIFACT.md`, `make reproduce-small`, Docker) |
| Ethics / data statements | Not stated | Data statement drafted in `docs/v2/SUBMISSION.md`: public data only, no personal data, terms per source |
| Supplementary material | Not stated | None planned; the anonymised artifact link replaces it |
| Conflicts of interest | Not stated on the page (entered in the submission system) | Owner lists them at submission |
