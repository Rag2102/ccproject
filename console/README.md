# console

Research Console: one static, read-only page (`index.html`) over one data file (`data/console.json`), built from `results/summary` at the current commit (ADR-002). It never blocks the paper.

```bash
make console                                   # or: make console-anon (double-blind build)
python3 -m http.server -d console 8040
```

| Tab | Week | Shows |
| --- | --- | --- |
| S1 Crossover | 22 | Saving against never migrating along ρ_L (default), or the pre-registered Δ against P2; the avoidance baselines (ADR-010) when present |
| S2 Trace Lens | 25 | Every Google 2019 τ-b measurement on the latent axis, with the C0 boundary and the break-even line |
| S3 Policy Lab | 25 | Why BAM and the threshold move one VM or not |
| S4 Run Matrix | 25 | Which cells of the frozen matrix are complete |
| S5 Paired Seeds | 31 | The 30 confirmatory comparisons with every seed as a dot, Holm status and the win and SD-rule checklist; or the same cells against P0 |
| S6 Figures | 34 | Every paper figure with its quoted macro values, source file and rebuild command (`results/figures/catalogue.yaml`) |

Notes:
- The plan names Observable Framework and DuckDB-wasm. The page stays a single HTML file over JSON instead: the per-seed values S5 needs are already in the summaries, so no Parquet reads in the browser and no build step.
- S6 previews are PNGs rendered with `pdftoppm` into `data/figs/` when it is installed; without it the tiles show no preview.
- Light and dark themes follow the system setting (toggle in the header); `prefers-reduced-motion` turns off chart animation; the layout works at 360 px.
- Not yet run: the axe, Playwright and Lighthouse checks (plan Week 34) need packages downloaded first.
