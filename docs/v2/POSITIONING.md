# Positioning sentence and first-page plan (Week 32, prepared 26 Oct 2026)

Plan Week 32, task 5: one sentence in the introduction that separates this work from Narya and from cost-sensitive thresholding, reused later in the cover letter. The paper's shape is decided at G3 (with the advisor) after the B/C results, so this file holds one candidate per shape. **Pick one at G3; do not put any of them in `intro.tex` before then.**

What every version must keep true:
- Narya (Levy et al., OSDI 2020) learns which mitigation action to take per flagged node from production outcomes, on private data, against a fixed action plan; it does not rank VMs by cost per unit of budget, and its avoid-allocation action is one of several.
- Cost-sensitive thresholding (Elkan 2001) is the classical decision rule; this work asks *when* it beats a well-tuned probability threshold under a migration budget, and measures whether that condition occurs.
- The exploratory avoidance finding (ADR-010) is post-freeze. It may lead the framing only if G3 and the advisor agree, and it is always labelled exploratory.

## Candidates

**Shape 1 (strong: BAM clears the bar in B, and the avoidance result is reported as exploratory)**
> Unlike Narya, which learns mitigation actions from private production outcomes, and unlike cost-sensitive rules taken as given, we measure the one quantity that decides whether ranking VMs by cost per GB beats a tuned probability threshold, show by a closed form that it is the spread of costs rather than their correlation with risk, and test the rule against a pre-registered bar on public data.

**Shape 2 (conditional: BAM helps against doing nothing but the 1% bar is met only in some regimes)**
> Where Narya learns which action to take and cost-sensitive learning prescribes how to rank, we ask when ranking matters at all: on public data and a pre-registered benchmark, cost-aware ranking pays only when costs per GB are spread out, and the measured correlation between criticality and risk is close to zero.

**Shape 3 (little benefit from migration ranking; avoidance leads)**
> Production systems such as Narya combine several mitigation actions; isolating them on public data with a pre-registered benchmark, we find that where new VMs are placed matters more than which VMs are moved: keeping arrivals off the riskiest hosts saves more than any migration ranking, including a cost-sensitive one.

## First-page checklist for the rewrite (Week 32)

- [ ] Shape chosen at G3; working title rewritten to match (current title assumes Shape 1).
- [ ] Abstract 150-200 words, numbers as macros, one-sentence takeaway (`main.tex`; the current abstract has no avoidance sentence and says "four Google cells" while the bound macro covers the three G1 cells: fix the wording).
- [ ] Contribution bullets reordered by strength; `scripts/v2/48_contribution_map.py` passes (every bullet has a ledger claim and a reference).
- [ ] If avoidance enters the first page, add a bullet with claim C9 and say "exploratory" in it.
- [ ] First figure chosen: F4b if Shape 2 or 3 (the comparison against never migrating), F3 or F4 if Shape 1.
- [ ] Cold read by someone new to the work (yours).
