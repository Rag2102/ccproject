# Task 4 — Time-to-Failure (TTF) Estimation: Results

## Approach: composition, not a new model

Task 3's hazard lookup table already contains `hazard_30d` — P(fail in this 30-day bin | survived to it) — for every (drive-model group, age) combination. That implies a full survival curve, S(t) = Π(1 − hazard_k) over all bins up to t. TTF is derived directly from that curve rather than trained separately:

- **Expected residual life** = the area under the conditional survival curve S(t | survived to now) — the standard "mean residual life" formula from reliability engineering, computed here by trapezoidal integration over 30-day bins.
- **Median residual life** = the first horizon at which that conditional survival curve drops below 0.5.

Keeping task 3 and task 4 on the same underlying hazard model (rather than fitting TTF independently) means the two signals the policy consumes — P(failure) and TTF — can't quietly disagree with each other; they're two views of one curve.

## A documented extrapolation assumption

Backblaze drives are observed out to ~8 years (max ~2,920 days), and very few drives are that old, so hazard estimates near the edge of the data are thin-sample, and anything past it is genuinely unknown. Rather than silently trusting the model to extrapolate, the script explicitly holds each model group's hazard constant at its last-observed-bin value for an additional ~16 years, purely to make the residual-life integral finite and computable. This is a standard reliability-engineering convention ("constant-hazard tail"), stated here so it isn't mistaken for a real prediction about 15-year-old drives.

One consequence worth knowing: **95.8% of (model group, age) combinations never see their survival curve drop below 50%, even with that generous tail** — i.e., for most model groups, "median time to failure" isn't a well-defined number because most drives of most models simply don't fail. This is realistic (annualized failure rates in the low single digits are normal for HDDs) but it does mean the mitigation policy should lean on **expected residual life**, not median, as its primary TTF signal — median TTF is kept in the output as a diagnostic, marked `n/a` when undefined rather than silently reporting a misleading tail-driven number.

## Face validity: does the predicted ranking match reality?

| model group | real failure rate | real median age at failure (days) | predicted expected TTF from age 0 (days) |
|---|---|---|---|
| ST3000DM001 (the flagged bad Seagate batch) | 36.3% | 760 | **2,691** |
| ST31500541AS | 18.1% | 1,540 | 6,706 |
| ST4000DM000 | 7.8% | 593 | 6,819 |
| HDS5C3030ALA630 | 3.2% | 1,237 | 8,111 |
| ST12000NM0007 (most reliable in the fleet) | 0.23% | 31† | 8,263 |

†Only 17 of 7,242 drives of this model actually failed, at low ages — too few events to trust that number on its own; it's a small-sample artifact, not evidence this model fails young.

The ranking is directionally right where it matters most: the one model group Backblaze itself publicly flagged as a bad batch (ST3000DM001) gets by far the shortest predicted TTF (2,691 days vs. 6,700–8,700 for everything else) — the model recovered a real, previously-known-bad cohort without being told about it.

## Concordance index (the actual verification metric)

Standard survival-model evaluation: sample pairs of real drives, check whether the one with the shorter predicted TTF is the one that actually failed first. Computed via Monte Carlo sampling (300,000 sampled pairs, 9,027 comparable) since exact computation over 122k drives is O(n²):

**C-index = 0.7145** (0.5 = random guessing, 1.0 = perfect ranking).

This is a meaningful, well-above-chance ranking signal for a genuinely hard problem (predicting which of two real hard drives fails first), and is consistent with the ROC-AUC (0.78) from task 3 — both numbers are telling the same story about how much real signal exists in (drive model, age) for this dataset.

## Output

- **`data/processed/ttf_lookup_table.csv`** (1,584 rows) — per (model group, age bin): `hazard_30d`, `survival_S`, `expected_ttf_days`, `median_ttf_days` (nullable), `median_ttf_beyond_tail` flag.
- `scripts/03_time_to_failure.py` — rerunnable (~10s), includes the face-validity table and C-index check inline so this verification reruns every time the model is retrained.

## Feeds into next

Tasks 3 and 4 together now give every host/VM at simulation time: `p_fail_within_window` (30-day lookahead) and `expected_ttf_days`. Task 5 (workload criticality + migration cost — already partly done in task 2's Azure preprocessing) and these two combine directly into task 6's cost-sensitive decision rule.
