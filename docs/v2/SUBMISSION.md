# Submission pack: paper A (plan Week 26, Appendix A.5)

Target: SoCC 2027 (VENUES.md), round 2, about early July 2027, unless the G3 verdict or the 2027 call changes it. The plan's rule: choose the venue from G3 and the current call, check the official page on the day you decide, and never submit to two venues at once.

Status key: [x] done and checked; [~] built and waiting on something named; [ ] not done. Owner items are marked (owner).

## Checklist

- [~] **Venue.** Chosen from the current call; deadline, page limit, template and anonymity rule recorded in `VENUES.md`.
  - SoCC 2026 rules are recorded and checked (5 Oct 2026).
  - The 2027 call is not out. Re-check on the day.
- [~] **PDF.**
  - Compiles from a clean checkout, fonts embedded, page and reference limits met.
  - `make paper` is wired up, but LaTeX is not installed yet (BasicTeX, owner; `paper/README.md`).
  - Then check fonts with `pdffonts paper/main.pdf` (every row "emb yes") and pages against 12 + references.
- [ ] **Authors** (owner).
  - Author list and affiliations, conflicts of interest, author contributions if required.
  - The draft is anonymous ("Anonymous").
- [~] **Anonymity.**
  - Anonymised artifact link (`RELEASE.md` §4).
  - No author names in the PDF metadata: acmart `anonymous` drops the author block; also check `pdfinfo paper/main.pdf` for the Author field.
  - Rename the benchmark in the submission if a preprint uses "VMMBench" (SoCC rule).
- [x] **Statements** (below): data availability, artifact, ethics. SoCC 2026 asks for none of them explicitly; they go in if the 2027 call asks, or as a short paragraph before the references.
- [ ] **Supplementary material.** None planned; the anonymised artifact link replaces it.
- [ ] **Preprint.** Post only if the advisor agrees and the venue allows it. SoCC allows it, with the renaming rule above (owner).
- [ ] **Backups** (owner, `RELEASE.md` §5): repo tag, Zenodo DOI, local copy, external copy.

## Data availability statement (draft)

All data used are public:
- **Backblaze Drive Stats** (drive-day records, 2013–2026), used under Backblaze's terms.
- **Google ClusterData 2019** (four cells, CC-BY).
- **Azure Public Dataset V1** (2017 VM trace, CC-BY-4.0 / MIT).

No proprietary or personal data was used. Raw third-party data is not redistributed. The artifact provides scripts that download each source and check it against published or recorded checksums, together with the processed extracts the simulator reads.

## Artifact statement (draft)

The artifact contains:
- the simulator;
- the policies;
- the frozen protocol and evaluation matrix;
- scenario cards with world hashes;
- every analysis script;
- the processed results behind each figure, table and number in the paper.

Every number in the paper is generated into a macro from those results. The artifact runs in three ways:
- `make reproduce-small` regenerates reduced versions of the main figures and Table 3 in minutes on a laptop;
- `make docker-repro` does the same in a clean container;
- `make reproduce` reruns the full study in about 14 hours on 8 cores.

Archived with a DOI at the release tag (link anonymised for review).

## Ethics statement (draft)

The study uses only public, aggregate infrastructure traces that contain no personal data and involves no human subjects. Results are from simulation; we make no claim about production performance at any provider.

## Next-cycle plan (the target deadline is later than Week 26)

The plan's rule: if the target deadline is later than Week 26, write a ten-week plan. Assuming SoCC 2027 round 2 (abstract and paper around 7–14 July 2027), there are about 14 weeks after Week 26. The next cycle uses ten of them; the rest is buffer.

| Weeks after W26 | Work | Done when |
| --- | --- | --- |
| 1–2 | Respond to the advisor's and readers' reviews (`REVIEW/responses.md`); revise | Every comment has a recorded response |
| 3–4 | One robustness result the reviews ask for most. Candidates: model-based worlds (deferred past Week 21, ADR-008), the risk-averse BAM variant, or a cost-tuned P2 as a second comparator | Result in the paper or in an appendix, logged as exploratory |
| 5–6 | Second dataset or proxy if G3 was not Strong: another public placement trace with a risk signal | Measured ρ with CI, reported beside G1 |
| 7 | Artifact polish: run `make docker-repro` on a second machine; fix every step a stranger trips on | A clean clone reproduces the small figures on a machine that is not this laptop |
| 8 | Preprint decision with the advisor; if yes, post with the renaming rule in place | Decision recorded in `LOG.md` |
| 9 | Language pass and page fit on the final template from the 2027 call | `make paper` within limits, `numbers --strict` passes |
| 10 | Submission checklist again; submit | Submitted, or the date fixed |

Phase 6 of the 60-week plan (testbed migration costs, Weeks 41–46) starts independently of this cycle and does not block the submission.
