# ADR-013: test destination-aware BAM and selective avoidance on fresh seeds
Status: **accepted** (owner asked to find new novelty, 2 Nov 2026; rule written before any run on these seeds)
Date: 2026-11-02

Context. Two things came out of explaining a robustness flag on dev seeds 101-110 only.

1. **BAM's collapse is about cost level, not steepness.** Week 20's `tiers_steep` (1, 3, 10) raised every tier against the migration resource term as well as widening the gap. Keeping the top weight at 1 with the same 1:10 ratio, (0.1, 0.3, 1), BAM improves (A3 +17.2%, B1 +6.7%). Keeping today's ratio but multiplying the level by 3.33, BAM collapses (A3 −54.7%, B1 −75.6%, 750,000+ migrations). The same happens with cheap migration (B1@G0-low −15.8%, 292,000 migrations). So this is consistent with N2, not against it. Cause proposed: `b = p c e − m` treats a moved VM as safe and is decided afresh every day, so once `m` is small against `c`, moved VMs are moved again.
2. **Marks need not close a host to everyone.** Closing the riskiest hosts per tier leaves them open to other tiers.

Neither is in Narya, NENYA or Deoxys as read: Narya's AIR counts interruptions on receiving nodes in the outcome, but no per-VM decision charges destination risk; Avoid closes a node to all VMs; none has per-VM criticality. Outside the 30-comparison family, the G3 rule and `PROTOCOL.md` v1.0.

## Policies (frozen)

- **P4-net**: BAM with `m + p_dst c`, where `p_dst` = E[min(p_a, p_b)] over two uniform up hosts, which is what the engine's destination rule delivers.
- **P0+selective**: closes the top q_t of hosts to tier t, q = (2%, 5%, 10%) for low, medium, high. Nothing migrates. A VM drawn onto a host closed to its tier is redrawn uniformly among up hosts that are open to it and have room.
- **Equal-closure comparators**, W = 4.4%, the GB-weighted mean of q over arrivals (tier GB shares 0.508, 0.317, 0.175): **P0+avoid(W)**, today's whole-host mark; **redirect(W)**, q = (W, W, W) with the same redraw as P0+selective, so the mechanism is the same and only the tiering differs.

## Primary tests

Seeds 4001-4050 (n = 50), regimes B1 and B2, budget argument 2%, oracle predictor. Paired by seed. Intervals are 95% BCa. p values are one-sided Wilcoxon signed-rank, Holm-corrected within each family.

**Family N (P4-net).** Settings: default, `level` (tier weights 1, 2, 3.33), `steep` (1, 3, 10), `G0-low`.
- N1, in 8 cells: P4-net saving against never migrating is above zero, Holm p < 0.05 and interval above zero.
- N2, in the 6 non-default cells: P4-net saving exceeds P4's, Holm p < 0.05 and interval above zero.
- N3, in the 2 default cells: P4-net − P4 has an interval lower bound above −1 point (non-inferiority).
**Confirmed** if all pass. **Partial** if N2 and N3 pass and N1 fails anywhere (each failure listed). **Not confirmed** otherwise.

**Family S (P0+selective), in each regime, against each comparator** (4 pairs).
- S1: saving difference has an interval lower bound above −1 point (non-inferiority).
- S2: rejected arrivals are lower, Holm p < 0.05 and the interval of the paired difference is below zero.
**Confirmed** if all 8 pass. **Partial** if all of S1 and the S2 pairs against P0+avoid(W) pass. **Not confirmed** otherwise.

## Secondary (reported, not part of the verdicts)

1. **Noise.** Persistent logit noise (ADR-012), σ ∈ {0.5, 1}, B1 and B2: P4, P4-net, P0+selective, P0+avoid(W), redirect(W). Known from dev seeds: P4-net stays negative at σ = 1 (B1 −16.9%). P4-net is not expected to fix noise, and this must be said.
2. **G0-high**, B1 and B2: P4, P4-net. Known from dev seeds: no real difference.
3. **Extended law.** S = φ Σ_t a_t R(q_t), a_t the tier's share of interruption cost among arrivals (0.268, 0.289, 0.443), φ and R frozen in ADR-012. Prediction: compared with the observed saving, B1 and B2.
4. **Migrations** per run for P4 and P4-net, as the test of the proposed cause. A fall alone does not prove re-migration.
5. **Combined** P4-net + selective, default cost only.

## Limits

Simulation, oracle hazards in the primary test. All comparators and q were looked at on dev seeds, and q was picked from a dev-seed grid, so only the seeds are blind. Rejected arrivals are about 0.02% of arrivals and 0.4% of arriving GB in B1, so S2 is a small absolute effect. Part of the rejection result may come from rank-based placement spreading load; the mechanism is not shown. Redirect differs from a whole-host mark as a mechanism, so comparing with redirect(W) isolates tiering and comparing with P0+avoid(W) does not. Written and frozen before the run but not committed to git before it: the SHA-256 is stored with the results, weaker evidence of order than ADR-011.

Implementation: `vmsim/policies/selective.py`, the `tier_block` hook in `vmsim/engine.py`, `scripts/v2/54_selective_net.py`; rows in `results/explore/selective_net/`, summary in `results/summary/selective_net.json`.
