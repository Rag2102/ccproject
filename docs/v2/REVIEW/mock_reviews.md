# Three adversarial reviews (Week 24, task 2)

Written against draft v2 (commit `1c8fdf5` onwards), in the personas of plan Appendix A.4. Each objection gets a response in the rebuttal table at the end. Where the objection is right, the paper changed, and the commit is recorded. Objections that depend on the numbers are marked **[after results]** and are answered once `results-frozen` exists.

## R1: systems

**Summary as R1 reads it.** A simulation study of which VMs to migrate under a daily GB budget, with a measured placement correlation and a closed-form theory.

**Weaknesses.**
1. **No deployment, not even a testbed.** Migration cost comes from a pre-copy formula with assumed bandwidth, dirty rate and concurrency. Real migrations fail, retry, contend with tenant traffic and are throttled by orchestrators. How much does the conclusion depend on the cost model?
2. **Drives stand in for hosts.** Most host failures in production are not disk failures (memory, CPU, PSU, firmware). The non-disk term is a Weibull you chose.
3. **Scale.** 2,000 hosts is a small cluster. Does anything change at 50,000?
4. **The daily cadence and the budget.** Narya acts on alerts within hours. A daily batch with a GB cap is one design among many; a NIC-time budget or a per-rack cap could change the ranking.
5. **P5 is not Narya.** Calling it "Narya-inspired" invites the comparison without earning it.
6. **The risk proxy.** A "long removal" in Borg is often decommissioning or a hardware refresh, not a failure.

## R2: ML / statistics

**Summary.** A pre-registered comparison of policies on paired seeds, Holm-corrected, with a calibrated failure model.

**Weaknesses.**
1. **The main matrix uses an oracle predictor.** The theory's assumption A1 (calibrated p) then holds by construction. The trained model, which reaches a PR-AUC of only about 0.07-0.10, enters only as robustness settings. The headline is an upper bound.
2. **Regression adjustment on realised failures.** Is this conditioning on a post-treatment variable?
3. **Multiplicity.** Holm covers 30 confirmatory comparisons, but the paper also shows dozens of exploratory cells and the Week 20 grid. Readers will treat them as findings.
4. **Thirty seeds, one cluster size.** Seeds test luck, not misspecification. The SD rule extends n but does not fix model error.
5. **Temporal validity of the failure model.** The last rolling-origin fold is much weaker (PR-AUC 0.044). Which fold is the simulator's predictor like?
6. **The latent-axis conversion.** Mapping τ-b to a Gaussian-copula ρ_L under each cell's margins is a modelling step. Is C0 robust to it?
7. **[after results]** Effect sizes against P0, not only against P2.

## R3: skeptic

**Summary.** "This is expected-cost thresholding on simulated data."

**Weaknesses.**
1. **Novelty.** Ranking by benefit density is Dantzig's knapsack greedy, and acting on expected cost is Elkan's rule. What is new?
2. **A straw-man comparator.** P2 is tuned to *spend the budget*, and the pilot shows it can cost several times more than never migrating. Beating it by 1% means little.
3. **Significance.** If critical work is uncorrelated with risk, and the advantage at ρ ≈ 0 depends on a cost spread you assumed, the practical question reduces to "how unequal are VM costs per GB?", which an operator can answer without this paper.
4. **[after results]** If BAM does not clear the 1% bar in the measured regime, is there a paper?
5. **Theory scope.** T3 holds for a one-shot decision under a Gaussian copula with equal weights. The simulator breaks all three. Why should the closed form guide anything?

---

## Rebuttal table

| # | Objection | Right? | Response | Change to the paper | Commit |
| --- | --- | --- | --- | --- | --- |
| R1.1 | No testbed; cost model assumed | Partly | Bandwidth and dirty-rate estimation errors (×0.5, ×1.5), concurrency (1-4) and downtime (5-20 min) are swept in Week 20, and the Morris ranking says which matter. A testbed measurement is planned (RQ6, Weeks 41-46) and stated as future work | Table of assumed elements (§8) lists each one and its range. The conclusion names testbed costs as next | 1c8fdf5 |
| R1.2 | Drives as hosts | Yes | A construct threat we cannot remove with public data. The non-disk multiplier is swept (0-3×) | Stated under construct validity (§8) | 1c8fdf5 |
| R1.3 | Scale | Partly | Scale was set by power, not realism (ADR-007): seeds, not hosts, carry the statistics. Policies act per host and per VM, so cluster size enters only through the budget share, which is swept | One sentence in the Evaluation setup **[after results]** | |
| R1.4 | Cadence and budget resource | Partly | The NIC-time budget is an ablation (P4-time, Week 20). Rack caps are RQ7 (Weeks 47-50) | Discussion names the alternatives | 1c8fdf5 |
| R1.5 | P5 is not Narya | Yes | Every difference is listed in the artifact (`narya_differences.md`). P5 is a baseline, not a claim about Narya | §9 says "Narya-inspired baseline whose every departure from the paper is listed" | 1c8fdf5 |
| R1.6 | Risk proxy | Yes | Three proxies, two weightings and three mappings give the same magnitude; we call it a proxy throughout | §5 and §8 | 1c8fdf5 |
| R2.1 | Oracle predictor | **Yes** | ADR-008 chose the oracle for the confirmatory matrix so that differences come from the policy. Noise (σ up to 2), miscalibration (γ 0.5-2) and drift are swept, and model-based worlds were deferred. The headline is therefore an upper bound under calibrated probabilities | Evaluation setup must say "oracle" and "upper bound"; Discussion internal validity **[change made with the Evaluation text]** | |
| R2.2 | Post-treatment adjustment | No | Failure times are drawn before any policy runs (common random numbers), so realised failures are the same for every policy on a seed: a pre-treatment covariate. The adjustment removes seed luck, not policy effect | One clause in the Evaluation setup | |
| R2.3 | Multiplicity | Partly | Only the 30 confirmatory cells carry claims; every other number is labelled exploratory in the text, tables and Console | Figure captions say "exploratory" **[check at the language pass]** | |
| R2.4 | Seeds test luck | Yes | Stated: replication on seeds 1001-1030 is reported as seed replication, and misspecification is covered by the robustness grid and Morris | §7 replication paragraph | |
| R2.5 | Fold variability | Partly | The oracle sidesteps it in the main matrix; the noise sweep covers a weaker predictor | §5 failure model mentions stability **[add one sentence]** | |
| R2.6 | Latent-axis conversion | No (for C0) | Every cell is C0 on the direct Spearman reading too (G1 §2), so the conversion does not decide the class | §5 already reports τ-b directly; add "C0 under the direct reading as well" | |
| R2.7 | Effects against P0 | **Yes** | ADR-005 required P0 and P3 beside P2 in every table, and the frozen Table 3 script omitted them. Fixed before any result was read | Table 3 gains P3 and P2-vs-P0 columns; companion table against P0 | e5560ed |
| R3.1 | Novelty | Partly | We claim neither rule (§3, §9). The contributions are the measurement, the closed form and its consequence (no break-even correlation; spread, not correlation, drives the gain), the pre-registered evaluation with a guard, and the benchmark | Contributions list in §1 says what is not claimed | 1c8fdf5 |
| R3.2 | Straw-man comparator | **Yes, partly** | The comparator was pre-registered (ADR-005) because operators spend budgets they are given. The objection is answered by showing P0 next to every number, not by changing the comparator after the fact | Table 3 P0 columns (e5560ed); the abstract and introduction state the result against P0 as well **[after results]** | |
| R3.3 | Significance | Partly | The theory turns "is there a break-even correlation?" (the prototype's question, and an expensive one to measure) into "how spread are costs per GB?", which an operator can read off their own fleet. That reduction is the practical contribution | Discussion: "when to use which policy" | 1c8fdf5 |
| R3.4 | No 1% win | **[after results]** | The protocol fixed three paper shapes in advance (strong, conditional, little benefit); a negative result is reported unchanged | Abstract and introduction written from macros, so they read correctly either way | 1c8fdf5 |
| R3.5 | Theory scope | Partly | T3 is used for direction and order of magnitude, not prediction. Section 6 of THEORY.md lists where the simulator breaks it, and F4 overlays the closed form on the simulated cells | §4 says so; F4 caption **[after results]** | |
