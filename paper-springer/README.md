# paper-springer

The research paper on the Springer Nature LaTeX template (journal article package, December 2024: `sn-jnl.cls` and the reference styles in `template/`, from the link in the course notice). The reference style is `sn-mathphys-num` (numbered); to switch, change the class option in `main.tex` and copy the matching `.bst` from `template/`.

## Build

```bash
make paper-springer
```

This regenerates the tables (`scripts/v2/56_paper_tables_postfreeze.py`, and Table 3 from `paper/tables/`), then compiles `main.pdf` with Tectonic (`brew install tectonic`) or `latexmk`.

## Who writes what

Every sentence of prose is the authors' own. `main.tex` holds only the template, headings, generated tables and figures, definitions taken from the code, and red `\guide{}` notes saying what each section should cover. Delete each note once its section is written. Before counting pages or submitting, set `\showguidefalse` in `main.tex` so no note prints.

Numbers come only from `paper/numbers.tex` (`make numbers`) and the generated tables. Never type a number by hand.

## Checklist against the course guidelines

| Guideline | Status (19 Nov 2026) |
| --- | --- |
| Springer LaTeX template | Done: `sn-jnl`, single column |
| At least 12 pages, excluding references | Not yet: 12 pages with notes shown; 9 with notes hidden, and references start on page 8, so about 7 pages are tables, figures and headings. Your prose has to add at least 5 more |
| GitHub link in the paper, working | Link is in Declarations (`\repourl`) and `refs.bib`. The repository is public. The local `v2-research` branch is ahead of GitHub, and `main` holds v1, so push the branch and point evaluators at it (or link to the branch URL) |
| Springer citation style | Done: `sn-mathphys-num` |
| Comprehensive literature review, recent journals and conferences | Not yet: `refs.bib` has 28 entries plus the repository; 8 are dataset or tool pages and 7 are papers from 2022 onward. Add recent journal and conference papers you have read |
| Original work, no AI-generated text presented as your own | Write all prose yourself. Fill in "Use of AI tools" in Declarations as your guide and the course rules require |
| Methodology, architecture, algorithms, implementation, setup, results, discussion | Headings, Algorithm 1, Figure 1 (architecture), the policy, stack and gap tables, and every results table are in place. All prose is still to write |
| Figures, tables and algorithms numbered, titled and referred to | Numbered and titled. Expand the four figure captions marked in red, and refer to every table and figure in your text |
| Comparison with existing approaches | Table 1 (scope) is in place. Section 8.6 needs your text; their headline figures come from live systems and different baselines, so they cannot be ranked against these simulated results |
| No fabricated results or references | Every table is generated from `results/summary`. Cite only papers you have read |
| No broken links or incorrect references | Every DOI and URL in `refs.bib` resolves (checked 19 Nov 2026; ACM and INFORMS pages block scripts, but their DOIs redirect to the publisher) |

## Open items found while setting up

- `pinheiro2007failure` is marked "citation only; not yet read" in `refs.bib`. Read it or drop it.
- `elkan2001foundations` has no DOI; Crossref has no record of it.
- Liu et al. (HPDC 2011) and Nathan et al. (SoCC 2015) are planned cost sources but are not read and not in `refs.bib`.
- `paper/sections/simulator.tex` had an open item: the node-log Weibull shape (0.7-0.8, Schroeder and Gibson) was taken from memory and must be checked before it is cited.
- Algorithm 1 is a summary of `vmsim/policies/bam.py`; check every step against the code before you describe it.
- `docs/v2/RESULTS_SELECTIVE_NET.md` rounds two B2 values differently from the generated table (whole-host closing 15.8 against 15.7; per-tier closing's lower bound 16.9 against 16.8). The table, read from `selective_net.json`, is the one to quote.
- Verification notes for each reference are kept in a `checked` field of `refs.bib`; BibTeX ignores it, so it never prints.
- The course notice leaves the deadline blank; confirm it.
