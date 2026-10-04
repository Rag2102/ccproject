# Cortez et al., Resource Central (SOSP 2017)

Source read: the Microsoft Research PDF, pages 1-8 of 15 (introduction, related work, workload characterisation, start of the system section; evaluation of the scheduler not read).

| Field | Notes |
| --- | --- |
| Problem | Characterise Azure's VM workload and show that its behaviours can be predicted, then serve predictions to resource managers. |
| Data | Every VM on Azure from 16 Nov 2016 to 16 Feb 2017 (first and third party); a sanitised subset is the Azure Public Dataset (section 3). |
| Baseline | Prior work on non-VM or synthetic workloads. |
| Metric | Distributions (size, lifetime, utilisation, deployment size) and prediction accuracy (79-90% across six metrics). |
| Claim | Many VM behaviours are consistent per subscription, so history predicts the future. |
| Limitation | Third-party IaaS VMs reveal little; workload class is inferred from CPU periodicity. |
| What we reuse | The V1 trace and its classes as the source of criticality tiers and VM sizes. |
| Reviewer would say | "Your criticality is a utilisation pattern, not business importance." |

## How the workload class is defined (the origin of v1's tiers)

- The class comes from an FFT of the average CPU series over at least 3 days: "potentially interactive" (diurnal pattern) or "delay-insensitive". VMs that do not last 3 consecutive days are "Unknown" (section 3.6).
- The classifier is conservative toward interactive: a delay-insensitive VM may be labelled interactive but not the reverse. Critical daily batch jobs may also be labelled interactive.
- Core-hours: about 28% interactive, about 68% delay-insensitive, the rest unknown. By VM count v1 found 58% Unknown, 39% delay-insensitive and 3% interactive, because most VMs are short-lived.
- So v1's "Unknown = medium criticality (weight 6)" is mostly "short-lived", and the 3 / 6 / 10 tier weights are assumptions. The robustness grid in W20 already tests "three tier-weight vectors"; add this caveat to the threats section.

## Ideas worth noting

- The paper lists "scheduling server maintenance" as a use: predicted VM lifetimes show when VMs end before maintenance, so migration may be unnecessary. v1 and v5 ignore VM lifetime in the policy. Narya's static strategy also waited 7 days for short-lived VMs. A lifetime-aware action is a candidate extension, not in the current scope.
- Spearman correlations between metrics (Figure 8): class and lifetime 0.21, utilisation and lifetime 0.11 to 0.20, so interactive VMs tend to live longer. This is a measured placement-free correlation, not a criticality-risk one.
