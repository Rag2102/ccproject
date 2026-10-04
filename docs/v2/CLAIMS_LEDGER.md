# Claims ledger (plan Week 22, task 4)

Every sentence of the abstract and introduction maps to one row: the evidence (figure, table or theorem), its interval, its family (confirmatory or exploratory) and its caveat. A claim with no row is not written. Rows marked **open** wait for the Week 18-21 runs and the G3 verdict (`G3_decision.md`); their wording follows the paper shape G1 × G3 decides, and negative results go in unchanged.

Started 5 Oct 2026. G1 = C0 (final). G3: open.

| # | Claim (draft wording) | Evidence | Interval / size | Family | Caveat | Status |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | In three Google 2019 cells, critical work is essentially uncorrelated with machine risk | `G1_decision.md`; trace F3; `\VGOneMaxAbsTauB` | \|τ-b\| ≤ 0.075 under every mapping and proxy; latent upper bound ≤ 0.082 | G1 (pre-registered gate) | Removal proxy, not failures; 79-166 long removals per cell; the sign depends on the mapping; no second source yet | ready |
| C2a | Under calibrated probabilities, the same budget and horizon-matched accounting, budget-aware selection never loses in expectation to a probability threshold | THEORY.md T1, T2 | Proved; smallest no-noise Δ in the grid +0.06% | Theory | One-shot model; fixed e; A1-A4 | ready |
| C2b | Its advantage is driven by the spread of costs and is largest near ρ = 0, not above a break-even correlation | THEORY.md T3; `theory_check.json` (3,024 / 3,024 points) | Closed form; MC within max(3 SE, 0.001) | Theory | One-shot; the simulator breaks it on purpose (Section 6 of THEORY.md) | ready |
| C2c | Noise in p alone does not reverse the advantage at ρ ≥ 0; flattening miscalibration can | THEORY.md T4 | 0 of 576 points negative at ρ ≥ 0 with γ = 1; down to −4.2% at γ = 0.5 | Theory | T4 as stated in the plan is partly false: reported as such | ready |
| C3a | In the realistic regimes (B1, B2), BAM [does / does not] beat the budget-tuned threshold by ≥ 1% | Table 3; `\VDeltaPFourBOneTwo` etc. | Bonferroni-simultaneous BCa, n = 30, Holm over 30 | Confirmatory | P2 is tuned to use the budget (ADR-005) and can cost more than never migrating; P0 and P3 are shown beside it | **open** |
| C3b | The guard P6 [captures ≥ 90% of the better policy's benefit on D and never loses > 1% to P2] | F8; `adaptive_D.json` | Per seed, n = 30 | Confirmatory (D) / exploratory | The fallback is the expensive P2 (owner decision) | **open** |
| C3c | The guard never switches on a control whose scores carry no information | P6 smoke; Week 18 noise control | 0 of 5 dev seeds (smoke); eval to come | Exploratory | Smoke on dev seeds | partly ready |
| C3d | SMART telemetry, not model class, carries the failure signal | `failure_model_v2.md`; ADR-006; `\VPrAucVOneFeatures`, `\VPrAucSMART` | PR-AUC 0.0018 → 0.074 (single) → 0.103 (ensemble, deployed); forward-in-time test | Exploratory | Drive-level; host-level composition assumed | ready |
| C4 | An open benchmark: scenario cards, hashed worlds, a result schema and a one-command reproduction | VMMBench, `make reproduce-small` (3.6 min) | n/a | Artifact | v0.9 at Week 25; hidden seeds at Week 53 | partly ready |
| C5 | A read-only console shows every number with its provenance | `console/` | n/a | Artifact, not a claim | Built from `vmconsole.json` at the tagged commit | skeleton |
| C6 | Robustness: which assumptions the conclusions depend on most | F6, F7, Morris (`w20_morris.json`) | μ* ranking | Exploratory | Morris on A3 only, 3 seeds per point, fast P2 tuner | **open** |
| C7 | Results replicate on fresh seeds | `confirmatory_replication.json` | n = 30 (seeds 1001-1030) | Replication | Tests luck, not simulator misspecification | **open** |
