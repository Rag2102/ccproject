# Gate G3: how strong is the evidence? (Week 21)

Status: **template**, written 5 Oct 2026 before any evaluation result. Filled in once the Week 18-21 runs exist. The verdict follows `PROTOCOL.md` v1.0 section 7 mechanically. Every box below cites the file that decides it, and none is filled by judgement.

## The rule (PROTOCOL.md section 7, copied)

| Verdict | Condition | Paper shape |
| --- | --- | --- |
| Strong | The win criterion holds for BAM or P6 over P2 in at least one real-trace regime (B1 or B2), theory matches simulation within tolerance, the seed replication agrees, and a second placement source agrees | 1, pays off |
| Medium | Wins only in synthetic or adversarial regimes while real ρ is below break-even; theory matches | 2, conditional |
| Weak | No robust effect, or theory and simulation disagree | 3, little benefit, plus the benchmark |

The win criterion (section 5): mean regression-adjusted Δ ≥ 1% and Holm-adjusted p < 0.05, Holm over all 30 confirmatory comparisons.

## Inputs (each read from a file, never re-run)

| Condition | Source | Value |
| --- | --- | --- |
| Holm over all 30 comparisons, scope "complete" | `results/summary/confirmatory.json` (`holm_scope`) | __ |
| Win for P4 or P6 in B1 or B2 (which cells) | same | __ |
| Wins in A3, A5, C only (for Medium) | same | __ |
| SD rule (ADR-007) triggered? Cells extended to n = 50? | same (`sd_rule_triggered`) | __ |
| Theory matches: closed form vs Monte Carlo within tolerance | `results/v2/theory_check.json`, `theory_recheck.json` | **yes: 3,024 / 3,024 (5 Oct 2026)** |
| Theory vs simulator, direction only (THEORY.md section 4): Δ ≥ 0 in every A and E cell beyond its CI; largest near ρ = 0; grows with σ_logκ | `results/summary/A.json`, `E.json`; F4 | __ |
| Seed replication agrees: the same cells win on seeds 1001-1030, and no cell flips sign beyond its CI | `results/summary/confirmatory_replication.json` | __ |
| Second placement source agrees | Week 21 task 3 (see below) | __ |
| Protocol check passed (completeness, no overspend, invariants) | `results/summary/protocol_check.json` | __ |
| Real ρ relative to break-even (interpretation only; G1 = C0 is final) | `G1_decision.md`, THEORY.md section 3 | real ρ ≈ 0 (C0) |

**Second placement source, status on 5 Oct 2026.** Alibaba 2018 was chosen (owner). Its machine metadata (verified checksums) has no machine-risk signal:
- all 4,034 machines are "USING" for the whole trace (one is "IMPORT_INSTALLING");
- no attribute ever changes;
- the repeated records are undocumented snapshots.

A risk proxy, and so a B-style calibration, therefore cannot be measured from it. The decision is open (owner); see the Week 21 tasks.

## Verdict

- G3 verdict: __ (Strong / Medium / Weak)
- Paper shape: __ (1 pays off / 2 conditional / 3 little benefit, plus the benchmark)
- Headline figure(s): __ ; supporting: __
- Venue tier (VENUES.md): __
- Signed off: ______  Date: ______

After sign-off: tag `results-frozen`. From then on, figures regenerate from `results/` files only (`make figures`), never by re-running the simulator.
