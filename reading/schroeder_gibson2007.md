# Schroeder and Gibson, Disk failures in the real world (FAST 2007)

Source read: the USENIX PDF, pages 1-9 of 14 (motivation, methodology, data sets, comparison with other components, replacement rates and age dependence). Time-between-failure statistics (section 5) not read.

| Field | Notes |
| --- | --- |
| Problem | Compare field disk replacement rates with datasheet MTTF and describe their statistics. |
| Data | Seven data sets from HPC and internet-services sites, about 100,000 drives, up to five years (Table 1). |
| Baseline | Datasheet MTTF of 1,000,000-1,500,000 hours, i.e. an annual failure rate of at most 0.88%. |
| Metric | Annual replacement rate (ARR), age-dependent ARR, the hazard rate of time between replacements. |
| Claim | ARR typically exceeds 1%, with 2-4% common and up to 13%; the weighted average was 3.4 times the datasheet value (Observation 1). Rates keep rising with age rather than showing a bathtub curve (Observation 5). |
| Limitation | Replacement is not failure: a vendor reported no problem found in 43% of returned disks (section 2.1). Conservative customer tests inflate ARR. |
| What we reuse | Age dependence for the hazard model, the replacement-vs-failure caveat, and the argument that disks are only part of host failures. |
| Reviewer would say | "Backblaze removal is not host failure; your hosts are drives." |

## Facts for the charter and threats section

- Disks were 30% and 49% of hardware replacements in two data sets, and 16% of node outages in HPC1 (Tables 2 and 3). Disks are not the main cause of node outages there; memory and CPU are. This supports the plan's non-disk hazard term (h_other) and the "drives are not hosts" threat.
- The authors report no infant-mortality spike and rising replacement rates from year 2. v1's Backblaze age-hazard shape is "not monotonic" (peaking at 1-3 years); check against this in W5.
- Time between replacements is not exponential and shows autocorrelation and long-range dependence (abstract; the supporting analysis is in section 5, which I did not read). Failures are therefore not independent, which motivates the correlated-failure scenarios R1-R3.
