# paper-springer

The research paper on the Springer Nature LaTeX template (journal article package, December 2024: `sn-jnl.cls` and the reference styles in `template/`, from the link in the course notice). The reference style is `sn-mathphys-num` (numbered); to switch, change the class option in `main.tex` and copy the matching `.bst` from `template/`.

## Build

```bash
make paper-springer
```

This regenerates the tables (`scripts/v2/56_paper_tables_postfreeze.py`, and Table 3 from `paper/tables/`), then compiles `main.pdf` with Tectonic (`brew install tectonic`) or `latexmk`.

## How it was written

The full text was drafted with an AI assistant (Claude, Anthropic) at the owner's request, after the project guide allowed AI use (conveyed in person, 19 Nov 2026). The "Use of AI tools" declaration in the paper says so. Every number comes from `paper/numbers.tex` (`make numbers`), the generated tables, or the summary files they are read from; nothing is invented. Read the whole paper before submitting: you must be able to explain and defend every part of it.

## Checklist against the course guidelines

| Guideline | Status (19 Nov 2026) |
| --- | --- |
| Springer LaTeX template | Done: `sn-jnl`, single column |
| At least 12 pages, excluding references | Done: 25 pages, references start on page 21, so 20 pages before them |
| GitHub link in the paper, working | Done: Implementation and Declarations link to the `v2-research` branch, and `refs.bib` cites the repository |
| Springer citation style | Done: `sn-mathphys-num` |
| Comprehensive literature review, recent journals and conferences | Done: 38 cited references, 16 of them papers from 2021 onward; five review subsections |
| Original work | The AI use is disclosed in the Declarations |
| Methodology, architecture, algorithms, implementation, setup, results, discussion | Done: Sections 3 to 10, with Algorithm 1 and Figure 1 (architecture) |
| Figures, tables and algorithms numbered, titled and referred to | Done: 5 figures, 14 tables and 1 algorithm, each referred to in the text |
| Comparison with existing approaches | Done: Section 8.6 and Tables 1 and 13 |
| No fabricated results or references | Every DOI and URL resolves; every table is generated from `results/summary` |
| Grammar, formatting, broken links | Compiles with no errors and no undefined references or citations; three small overfull lines remain (at most 18 pt) |

## Left for you

- **Placeholders:** your co-authors' names and emails, the institution and city, the guide's name in the acknowledgements, and the author-contribution statement.
- **Recent papers read only from their abstracts:** 10 of the new references (`checked` field in `refs.bib` says "full text not read"). Read each one before you defend the literature review.
- **Cost sources:** Liu et al. (HPDC 2011) and Nathan et al. (SoCC 2015) are still unread, so the cost range uses 4 of 6 planned sources, as the paper says.
- **Algorithm 1:** a summary of `vmsim/policies/bam.py`; check it against the code.
- **`elkan2001foundations`** has no DOI; Crossref has no record of it.
- **Rounding:** `docs/v2/RESULTS_SELECTIVE_NET.md` rounds two B2 values differently from the generated table (15.8 against 15.7; 16.9 against 16.8). The table, read from `selective_net.json`, is the one to quote.
- **Deadline:** the course notice leaves it blank; confirm it.
- Verification notes for each reference are kept in a `checked` field of `refs.bib`; BibTeX ignores it, so it never prints.
