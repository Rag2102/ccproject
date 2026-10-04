# Xu et al., Improving Service Availability of Cloud Systems by Predicting Disk Error (USENIX ATC 2018)

Source read: the USENIX open-access PDF, the whole paper (pages 481-492 of the proceedings: sections 1-7, with section 6 skimmed). Pages 1-6 were read on 4 Oct; the rest on 4 Oct for this note.

| Field | Notes |
| --- | --- |
| Problem | Predict which disks in Azure compute clusters will show *disk errors* (sector, latency, timeout: "gray failures") soon, so their VMs can be live-migrated and new VMs placed on healthier disks (section 2.2). |
| Data | Microsoft production data, labels from engineers' root-cause analysis of service issues. Train on October 2017, test on three parts of November 2017. About 3 faulty disks per 10,000 per day (section 4.1). 457 candidate features: SMART plus system-level signals such as FileSystemError, DeviceReset, VMFrozen, with window statistics Diff, Sigma and Bin over 3, 5 and 7 days (section 3.1). |
| Baseline | Random Forest and SVM on SMART only; weighted classification and SMOTE for the ranking part. |
| Metric | ROC-AUC; TPR at FPR = 0.1%; misclassification cost = 3 × FP + 1 × FN (Table 3, Table 4). |
| Claim | CDEF (stable-feature selection plus a FastTree learning-to-rank model with a cost-minimising cut-off r) has TPR 29.7-41.1% at FPR 0.1%, against 18.8-34.1% for Random Forest (Table 3). In production it saves about 63k VM-downtime minutes a month (section 5). |
| Limitation | One company, one month of training. Labels are noisy, since repaired disks return (section 4.5). The cost ratio 3:1 is set by experts, not measured. No precision/recall or calibration is reported. The ranking model gives no probabilities, so its output cannot be put into an expected-cost rule directly. |
| What we reuse | (1) **Temporal splits.** Cross-validation gave TPR 91.6% where online prediction gave 36.5% on the same data (section 4.4, Figure 7). This is the strongest published warning against the random split v1 used. (2) Diff and window features for Week 7 (`11_features.py`). (3) Their deployment: retrain daily on a 90-day moving window, mark the node unallocatable, live-migrate, then stress-test the disk. That is the operational pattern our "migrate" and "avoid-allocation" actions model. (4) "The cost to recover a node with one VM on top is much cheaper than ... with 10 VMs" (section 5): the per-host cost differences that BAM ranks on. |
| Reviewer would say | "Azure already does disk-error-aware migration with a cost-sensitive cut-off; what does BAM add?" Answer: CDEF picks r by a fixed FP:FN cost ratio for all disks. BAM uses each host's own VM mix (criticality, size) under a migration budget, and asks when that beats a threshold. |

## Facts for the charter, labels and threats

- **Lead time.** Disk errors appear on average 15.8 days before complete failure, and reallocated sectors triple in the last week (section 5). Backblaze's `failure = 1` is complete failure, so our labels mark the *later* event. With only SMART, part of this lead is invisible to us. This supports reporting H = 7 and 14 next to the primary H = 30 (`docs/v2/label_spec.md`).
- **Positive rate.** 3 in 10,000 per day is about 11% a year, far above Backblaze's AFR of about 1.5%, because errors are a much wider event than failures. Do not compare their TPR numbers with ours.
- **Rack effects.** They give "disks on the same rack or the same motherboard encounter similar attribute changes caused by unstable voltage" (section 4.4) as a reason random splits leak. It is also direct evidence of correlated failures within a group, which motivates the correlated regimes R1-R3 and the Week 4 group columns.
- **Continuous training.** Failure distributions drift with firmware, workload and maintenance (section 5). This supports regime D (non-stationary) and the rolling-origin split in Week 7.

Citation: `xu2018cdef` in `paper/refs.bib` (checked on the USENIX page in Week 2; the PDF's first page confirms ATC '18, Boston, July 2018, ISBN 978-1-939133-02-1).
