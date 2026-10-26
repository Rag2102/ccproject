# Licence review of what the artifact redistributes (Week 36, prepared 26 Oct 2026)

Plan Week 36, task 4: re-read each dataset's terms and fetch instead of redistributing where needed. The terms below are as recorded in `data_sources.md` (read 4 Oct 2026). **Re-read them in Week 36 proper (June 2027)** and update the "Terms read" column; terms pages change.

## Tracked data files (git ls-files data)

| File(s) | Origin | Terms | Status |
| --- | --- | --- | --- |
| `data/raw/azure/*` (vmtable, sosp_data_*, schema) | Azure Public Dataset V1 | CC-BY-4.0 and MIT (dual); cite the SOSP'17 Resource Central paper | OK to redistribute with attribution (NOTICE says so) |
| `data/processed/azure_vms_*` | derived from the above | same | OK |
| `data/raw/backblaze/backblaze_2013_2017_hdd_survival.csv` | **a third-party per-drive summary of Backblaze 2013-2017, with no licence file** (v1 input) | Backblaze: cite, user solely responsible, derivative works may be sold but not the data itself. The third party's own terms: **unknown** | **Owner decision needed** (below) |
| `data/processed/backblaze_drives_clean.csv`, `hazard_lookup_table.csv`, `ttf_lookup_table.csv`, `backblaze_failure_rate_by_*.csv`, `kaplan_meier_comparison.csv` | derived from that summary by v1's scripts | Backblaze's terms allow derivative works; the summary's terms are unknown | Same decision |
| other `data/processed/*` (simulation, policy, importance tables) | v1 outputs | ours (Apache-2.0) | OK |
| Google 2019 extracts | not tracked; rebuilt by `fetch_data.sh` and `13_trace_rho.py` | CC-BY 4.0 | OK (fetched, not redistributed) |
| Backblaze 2013-2026 archives | not tracked; fetched by `fetch_data.sh` (35 GB) | as above | OK (fetched) |

## The decision: v1's third-party Backblaze summary

The frozen simulator samples drives and their hazard from the v1 tables (`vmsim/entities.py` reads `backblaze_drives_clean.csv`; `vmsim/failure.py` uses v1's hazard lookup), so these files are inputs to every evaluation run. Changing them now would change frozen inputs. Options:

1. **Keep them in the artifact**, stating their provenance in NOTICE and the artifact appendix, and citing Backblaze as its terms ask. Lowest effort; the open question is only the third party's compilation rights.
2. **Ship a script instead of the files**: fetch the third-party summary from its original location at build time (if it is still public), and check it against `data/CHECKSUMS.sha256`. Keeps runs identical; needs the original URL, which the repository does not record.
3. **Rebuild the tables from the Backblaze archives** v2 already ingests. Removes the third party, but changes the simulator's inputs after the freeze: it would need a logged post-freeze change and a rerun, so not before the paper.

Recommendation: option 2 if the original source can still be found (record it in `data_sources.md`), otherwise option 1 with the provenance stated. Either way, NOTICE should name the file and its origin.

## Other licence points

- The Apache-2.0 licence (LICENSE, NOTICE) covers code and our processed results, not third-party data; NOTICE already says so.
- `docs/VM_Mitigation_Policy_Presentation.pptx` and the v1 report name the author: hide them in the anonymous repository view (`45_anon_check.py` lists every such file).
