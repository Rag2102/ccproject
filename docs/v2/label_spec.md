# Label specification (Week 5)

Written before any model is trained. The model, splits and features are Week 7; this note fixes only what a positive example is. The protocol's one-horizon rule (`PROTOCOL.md` section 4) applies: the horizon a probability is trained for is the horizon over which the simulator credits a migration.

## Unit and notation

- A **prediction point** is a drive-day (serial, d): the model sees everything the drive reported up to and including day d, and predicts the next H days.
- f = the drive's **failure day**: the date of its first row with `failure = 1`. Rows after f are dropped. The quality report counts the drives that report after a failure; none of their later rows are used.
- L = the drive's **last observed day**: f for a failed drive, otherwise its last row.
- E = the last day of the data, or of the split period the point belongs to (see "Splits").
- Horizons H ∈ {7, 14, 30} days. **H = 30 is primary** because the simulator decides in 30-day bins. 7 and 14 are reported for comparison with the disk-prediction literature.

## Rule

For each drive and each day d on which it reported (missing days are not prediction points):

| Case | Label for horizon H |
| --- | --- |
| The drive fails and d < f with f − d ≤ H | **1** |
| The drive fails and f − d > H | **0** |
| d = f (the failure day itself) | **excluded**: on that day the failure is already known, and the SMART values may show it |
| The drive does not fail in the data and d ≤ L − H | **0** |
| The drive does not fail in the data and d > L − H | **excluded (censored)**: it could still fail within H days after its last row, and we would never see it. Counting these as 0 would create false negatives |

The censoring rule applies the same way to:
- a drive that is still running at the end of the data;
- a drive that leaves the data without a failure flag (decommissioned or moved).

Backblaze does not record why a drive stops reporting, so the two cases cannot be separated. Treating both as censored is the conservative reading.

## Splits

For a point in a split period ending on E_split, the label must be decided inside that period. A point with d > E_split − H, whose drive has not failed by E_split, is excluded from that period. Otherwise the training label would look into the validation or test period.

Week 7 also excludes from training any drive whose failure day falls in the test period. That is a stricter rule than this one, and it is kept.

## Derived targets

- **Discrete-time hazard.** h(d) = P(f = d + 1 | alive at d, features). This is the H = 1 case of the rule above. The person-period table has one row per prediction point with y = 1 only on the day before f.
  - Any horizon follows from it: p_H(d) = 1 − ∏_{k=0}^{H−1} (1 − h(d + k)), with features held at day d.
  - The same hazard gives the expected time to failure that v1 used (TTF), so urgency stays available.
- **Calibration target.** The simulator uses p_30, the probability that the host's drives fail within the next 30 days. A host with d drives fails if any drive fails: p_host = 1 − ∏ (1 − p_30,i). This assumes independent drives, an assumption the Week 4 group columns can test.

## Expected prevalence

At a fleet AFR of about 1.5% a year (Week 5 table), the share of positive prediction points is about AFR × H / 365:
- about 0.03% at H = 7;
- about 0.06% at H = 14;
- about 0.12% at H = 30.

That is about one positive per 800 points at H = 30. The plan's metrics follow from this: PR-AUC, precision at the top 1% and 5%, and no class weights, so probabilities stay calibrated.

## Edge cases

| Situation | Rule |
| --- | --- |
| More than one `failure = 1` row | The first one is f; the others are dropped with every row after f |
| A serial reported under two models | One drive; model = the one it reported on most days (life table rule) |
| Day-to-day decrease in power-on hours | Not a label issue. Age features use the running maximum (quality report section 3) |
| Days when the whole fleet under-reports (quality report section 4) | No prediction points on days a drive did not report; labels use the failure flag only, never absence |
| A drive whose first row is a failure | No prediction points; it counts in the life table and the AFR |
