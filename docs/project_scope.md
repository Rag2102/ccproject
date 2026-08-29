# Project Scope — Cost-Sensitive, Workload-Aware VM Failure Mitigation

## 1. Problem statement

A workload-aware, cost-sensitive mitigation policy that incorporates failure probability, estimated time-to-failure (TTF), workload criticality, and migration cost can reduce customer-impacting VM failures while minimizing unnecessary migrations, compared with probability-threshold-based mitigation.

## 2. Related work

**Narya (Microsoft Azure).** Published at OSDI 2020 as "Predictive and Adaptive Failure Mitigation to Avert Production Cloud VM Interruptions," later productized as Project Narya. It runs three stages: predict host failure from fleet telemetry (a mix of hand-written rules — e.g. two CPU IERR events within 30 days — and ML models), pick a mitigation action, then measure customer impact to keep improving. Available actions: mark the node unallocatable, live-migrate VMs off it, do a soft kernel reboot that preserves memory state, deprioritize new allocations to it, or send the host to physical repair. Rather than an explicit cost formula, Narya picks among these actions using online A/B experimentation and reinforcement learning, tuned to maximize customer experience empirically. In production it cut VM interruptions by roughly 26% over 15 months versus the prior static strategy.

The gap this project targets: Narya's decision layer is a learned policy (bandit/RL) whose reward shaping isn't published, and it doesn't describe an explicit, interpretable function of failure probability, urgency, workload criticality, and migration cost. This project builds and evaluates that explicit cost-sensitive decision rule, and benchmarks it against the simpler baseline most systems actually use.

**Probability-threshold-based mitigation (baseline).** Migrate/mitigate any host or VM whose predicted P(failure) exceeds a fixed threshold τ, regardless of how soon the failure is likely (TTF), how important the workload is, or how expensive the migration would be. This is the common industry baseline, and functionally similar to the "static strategy" Narya's own paper benchmarks against.

Sources:
- [Narya: Predictive and Adaptive Failure Mitigation to Avert Production Cloud VM Interruptions — Microsoft Research](https://www.microsoft.com/en-us/research/publication/predictive-and-adaptive-failure-mitigation-to-avert-production-cloud-vm-interruptions/)
- [Advancing failure prediction and mitigation — introducing Narya — Azure Blog](https://azure.microsoft.com/en-us/blog/advancing-failure-prediction-and-mitigation-introducing-narya/)
- [OSDI'20 technical report (PDF)](https://www.microsoft.com/en-us/research/wp-content/uploads/2020/08/OSDI_tech_report.pdf)

## 3. Formal problem framing

For each host/VM at each decision point, define four signals:
- **p_fail** — predicted probability of failure within a lookahead window
- **TTF** — estimated time-to-failure (urgency; a host at p_fail=0.6 failing in 2 hours is very different from one failing in 2 weeks)
- **criticality (c)** — importance tier of the workload running on the VM (e.g. customer-facing/production vs. batch/delay-insensitive)
- **migration_cost (m)** — cost of migrating this VM now (function of VM size, live-migration duration, expected downtime/blackout)

**Decision rule (cost-sensitive policy):** migrate when the expected cost of *not* acting exceeds the cost of acting:

  expected_cost_of_inaction = p_fail × urgency_weight(TTF) × criticality_weight(c)
  trigger migration if expected_cost_of_inaction > migration_cost(m)

**Baseline rule:** migrate if p_fail > τ (fixed threshold, no urgency/criticality/cost term).

**Outcomes to score, per decision:**
- *Customer-impacting failure* — host/VM failed and was NOT migrated in time (or wasn't migrated at all) → the harm this project wants to reduce.
- *Unnecessary migration* — VM was migrated but the host never actually failed in the window → the churn/cost this project wants to avoid.
- *Necessary migration* — VM was migrated and the host did fail shortly after → correct call.
- *Cost saved* — net of migration costs incurred vs. failures avoided, weighted by criticality.

## 4. Success criteria

1. Lower rate of customer-impacting failures than the threshold baseline, at equal or fewer total migrations.
2. Lower rate of unnecessary migrations than the threshold baseline, at equal or better failure-avoidance.
3. A cost-weighted objective (failures avoided, weighted by criticality, minus migration costs incurred) that is higher than the baseline's.
4. Sensible sensitivity: tightening the criticality or cost weight should predictably shift the migrate/don't-migrate boundary (used as a sanity/ablation check, not just a headline number).

## 5. Datasets (both real, combined — no fully real linked "host failure + VM workload" dataset is public; that internal linkage is exactly what makes Narya possible at Microsoft)

| Role in project | Dataset | What it actually provides | Real? |
|---|---|---|---|
| Failure probability + TTF ground truth | **Backblaze Hard Drive Stats** (daily SMART telemetry per drive, quarterly CSV releases from 2013–present, `backblaze.com/cloud-storage/resources/hard-drive-test-data`) | Per drive-day: `date`, `serial_number`, `model`, `capacity_bytes`, `failure` (1 on the day a drive fails, else 0), and ~20 raw+normalized SMART attributes (reallocated sectors, reported uncorrectable errors, temperature, power-on hours, etc.). TTF is derived by counting backward from each drive's failure day. This stands in for "host health telemetry," the same role Azure's internal fleet telemetry plays for Narya. | Real, genuine failures |
| Workload criticality + migration cost proxy | **Azure Public Dataset V2** (Microsoft's own released VM trace, `github.com/Azure/AzurePublicDataset`) | Real Azure VM trace: ~2.7M VMs over 30 days, with `VM category` (Delay-insensitive / Interactive / Unknown — a natural criticality tier), virtual-core-count bucket and memory-GB bucket (a natural migration-cost proxy — bigger VM ≈ costlier/slower to live-migrate), plus 5-minute CPU utilization and VM creation/deletion timestamps. | Real, genuine workload trace |

**How they're combined:** simulate a fleet of hosts, each host's health trajectory replayed from one real Backblaze drive's history (drive failure → host failure proxy); each host hosts one or more VMs drawn from the real Azure trace, contributing that VM's real criticality tier and size/cost proxy. The only synthetic step is *which* VM sits on *which* host — everything each side reports (failure behavior, workload behavior) is real telemetry.

## 6. Do we need a full cloud simulator?

**No — and a general-purpose one (CloudSim, SimGrid, etc.) would be the wrong tool.** Those simulate scheduling, energy, and network behavior across a datacenter; they don't have a notion of "predicted failure probability" or "mitigation policy" built in, and bolting that on would burn a large fraction of a 2-week timeline on simulator plumbing instead of the actual research question.

What's needed instead is a small, purpose-built **replay/evaluation harness** (~day 8 in the task plan): a day-by-day loop that (1) advances each host's real Backblaze-derived health state, (2) feeds current signals to both the cost-sensitive policy and the threshold baseline, (3) executes whichever decision each policy makes, and (4) scores the four outcome buckets above. This is "simulation" in the sense of a controlled replay, not a datacenter simulator platform — it should be well under a day of engineering once the data pipeline (task 2) is ready.

## 7. Scope boundaries for the 2-week window (explicitly out of scope)

- No actual live-migration mechanics (VMware/Hyper-V internals) — migration is modeled as a cost + outcome, not executed.
- No reinforcement-learning policy like production Narya — an explicit, interpretable analytic cost rule is used instead, since it's evaluable and explainable in the time available, and is the actual novelty claim in the problem statement.
- Single simulated region/fleet, no network topology or cross-host contention modeling.
- Criticality tiers taken directly from the Azure trace's `VM category` field rather than a custom business-impact model.
