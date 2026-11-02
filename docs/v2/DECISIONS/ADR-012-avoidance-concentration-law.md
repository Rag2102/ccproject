# ADR-012: test a concentration law for avoidance on fresh seeds
Status: **accepted** (owner asked for more novelty over the base papers, 1 Nov 2026; rule written before any run on these seeds)
Date: 2026-11-01

Context. ADR-011 confirmed that marking the riskiest hosts saves cost, but gave no reason for its size. Narya has Avoid as one action its bandit chooses; none of the three base papers says when avoidance pays or how much. Dev seeds suggest a simple law. This ADR tests it where nothing has been seen. It does not touch the 30-comparison family, the G3 rule or `PROTOCOL.md` v1.0.

## The law (T5)

A new VM lands in proportion to free capacity. Marking the top q of hosts sends arrivals to the rest. If L(q, σ) is the share of the fleet's true failure risk held by the q of hosts ranked highest under a predictor with logit noise σ, the mean risk seen by a new VM falls by

R(q, σ) = (L(q, σ) − q) / (1 − q).

The saving against never migrating is then S(q, σ) = φ · R(q, σ), where φ is the share of interruption cost that placement can reach (φ ≤ 1 if VMs placed before a mark stay exposed). The law implies: the gain depends on how concentrated risk is, not on cost spread; it falls to zero when scores carry no information; and it does not go negative.

## Frozen inputs

- R(q, σ): computed from the oracle's p_H on **dev seeds 101-110 only**, in B2's world (hazards are the same in B1 and B2), by `scripts/v2/52_avoid_law.py --derive`, written to `results/summary/avoid_law_R.json`. Host risk is heavy-tailed, so L is empirical, not the lognormal form.
- φ: one number per regime, from the ADR-011 result already published at q = 2%, σ = 0: φ = S / R(2%, 0). B1: 11.21 / 11.91 = 0.94. B2: 8.93 / 11.91 = 0.75.

## Primary test

- Seeds 3001-3050 (n = 50), regimes B1 and B2, budget argument 2%, policy P0+avoid.
- Cells: q ∈ {0.5, 1, 2, 5, 10}% × noise σ ∈ {0, 0.5, 1, 2}, where noise is persistent: one draw per host per 30-day block. That is 20 cells. The anchor (q = 2%, σ = 0) is left out of the scores, so 19 are out of sample.
- Measure: mean saving per cell against P0 on the same seed.
- In each regime: **Spearman ≥ 0.9** between predicted and observed, and **mean absolute error ≤ 2 points**.
- **Supported** if both hold in both regimes. **Direction only** if Spearman holds in both but not the error. **Not supported** otherwise. The label follows this rule, and every cell is reported.

Known before the run, from dev seeds and ADR-011: the law looks close on q, and overshoots daily-redrawn noise at q = 2% (B1, σ = 1: predicted 6.1, ADR-011 measured 3.8). Persistent noise was chosen because real predictor errors persist and because dev seeds looked closer under it. So the noise cells are not a blind choice of form, only blind seeds. A failure at q = 10% would be read as capacity: the law ignores rejected arrivals.

## Secondary (reported, not part of the verdict)

1. **Prediction quality needed.** Same seeds, q = 2%, budget 2%, persistent noise σ ∈ {0.1, 0.25, 0.5, 1}: P0+avoid, P4 (BAM), P5, and P4-c, BAM with mean-corrected noise (log-odds shifted by −σ²/2), so that noise alone does not inflate its mean p. Report the saving and the σ at which each crosses zero, by interpolation.
2. **Rejected arrivals** per q, against P0. The law has no capacity term.
3. **Shuffled control**, q = 2%, in B1, B2, A1 and B1 with `arrival_blend` removed, to explain the leftover in B1 (+1.6% in ADR-011). Hypothesis from dev seeds: random marks break the tier-risk alignment of B1's rank-based placement, so the leftover is about placement, not information.
4. **Daily noise** at q = 2%, σ = 1, for comparison with ADR-011.

## Limits

Simulation only, oracle hazards underneath. φ is fitted, one number per regime, and is not explained by this test. The law predicts levels only given φ, and shapes without it. A pass supports a description of this simulator's behaviour. It does not show that real fleets behave this way. Written and frozen before the run, but not committed to git before it, unlike ADR-011: the file's SHA-256 is stored with the results instead, which is weaker evidence of order.

Implementation: `scripts/v2/52_avoid_law.py`; rows in `results/explore/avoid_law/`, summary in `results/summary/avoid_law.json`.
