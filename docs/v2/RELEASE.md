# Release steps: v2.0 (plan Week 25)

Owner-run: tags, the GitHub release and the Zenodo upload are yours. Run these only after `results-frozen` is tagged (G3) and the advisor has seen the draft.

## 1. Checks (any machine with the venv)

```
make release        # checksums, numbers --strict (no placeholders left), all tests
make docker-repro   # Table 3 (small) from a clean container matches this machine
```

## 2. Tag and push

```
git -C ~/Desktop/ccproject tag -a v2.0 -m "v2.0: paper A artifact (results-frozen + paper draft v3)"
git -C ~/Desktop/ccproject push origin v2.0
```

## 3. Zenodo

1. On zenodo.org, sign in with GitHub and switch on the `Rag2102/ccproject` repository (Settings → GitHub).
2. Create a GitHub release from the tag `v2.0`. Zenodo archives it and mints a DOI. `.zenodo.json` supplies the title, licence and description.
3. Put the DOI in `CITATION.cff` (`doi:`) and the paper's artifact statement, and commit.

Only code, configs and processed results go into the archive. Raw third-party data stays out; `scripts/v2/fetch_data.sh` downloads it, and `data/CHECKSUMS.sha256` checks it.

## 4. Anonymised link for review (dual-anonymous venues)

Create an anonymised mirror of the tagged commit (for example anonymous.4open.science). Then check that the mirror shows:
- no author names in `CITATION.cff`, `NOTICE`, `LICENSE` or commit metadata;
- no GitHub URL in `README.md` or `ARTIFACT.md`.

Use that link, not the GitHub URL, in the submission.

## 5. Backups (Week 26)

You need four copies:
- the repo tag;
- the Zenodo DOI;
- a local copy of `results/` (`results/raw` is not in git; about 1 GB after the runs);
- an external drive or cloud copy of the same.
