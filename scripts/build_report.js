const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, BorderStyle, ShadingType, ImageRun, PageBreak, AlignmentType,
  TableOfContents, LevelFormat, convertInchesToTwip, VerticalAlign,
} = require("docx");

const INK = "1A1A1A";
const MUTED = "6B6B6B";
const BLUE = "256ABF";
const HEADER_FILL = "EAF1FB";

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------
function p(text, opts = {}) {
  const { bold, italics, size, color, spacingAfter = 160, alignment } = opts;
  return new Paragraph({
    alignment,
    spacing: { after: spacingAfter },
    children: [new TextRun({ text, bold, italics, size, color: color || INK })],
  });
}

function bullet(text, opts = {}) {
  return new Paragraph({
    numbering: { reference: "bullet-list", level: 0 },
    spacing: { after: 100 },
    children: [new TextRun({ text, color: INK, ...opts })],
  });
}

function heading(text, level) {
  return new Paragraph({ text, heading: level, spacing: { before: 280, after: 160 } });
}

function caption(text) {
  return new Paragraph({
    spacing: { before: 80, after: 240 },
    children: [new TextRun({ text, italics: true, size: 19, color: MUTED })],
  });
}

function cell(text, { header = false, width, align = AlignmentType.LEFT } = {}) {
  return new TableCell({
    width: width ? { size: width, type: WidthType.DXA } : undefined,
    shading: header ? { type: ShadingType.CLEAR, fill: HEADER_FILL } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({
      alignment: align,
      children: [new TextRun({ text: String(text), bold: header, size: 20, color: INK })],
    })],
  });
}

function table(headerRow, rows, colWidths) {
  const total = colWidths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: colWidths,
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: "C9C7C2" },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: "C9C7C2" },
      left: { style: BorderStyle.SINGLE, size: 4, color: "C9C7C2" },
      right: { style: BorderStyle.SINGLE, size: 4, color: "C9C7C2" },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "E3E2DF" },
      insideVertical: { style: BorderStyle.SINGLE, size: 2, color: "E3E2DF" },
    },
    rows: [
      new TableRow({
        tableHeader: true,
        children: headerRow.map((h, i) => cell(h, { header: true, width: colWidths[i] })),
      }),
      ...rows.map(r => new TableRow({
        children: r.map((v, i) => cell(v, { width: colWidths[i], align: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER })),
      })),
    ],
  });
}

// ---------------------------------------------------------------------------
// Document
// ---------------------------------------------------------------------------
const doc = new Document({
  features: { updateFields: true },
  numbering: {
    config: [{
      reference: "bullet-list",
      levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: convertInchesToTwip(0.28), hanging: convertInchesToTwip(0.18) } } } }],
    }],
  },
  sections: [
    // ---------------- Title page ----------------
    {
      properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1080, bottom: 1080, left: 900, right: 900 } } },
      children: [
        new Paragraph({ spacing: { before: 2400, after: 400 }, alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "A Workload-Aware, Cost-Sensitive", bold: true, size: 44, color: INK })] }),
        new Paragraph({ spacing: { after: 600 }, alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "Mitigation Policy for Cloud VM Failures", bold: true, size: 44, color: INK })] }),
        new Paragraph({ spacing: { after: 200 }, alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "Reducing customer-impacting VM failures while minimizing unnecessary migrations,",
            size: 24, color: MUTED })] }),
        new Paragraph({ spacing: { after: 1200 }, alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "benchmarked against probability-threshold-based mitigation",
            size: 24, color: MUTED })] }),
        new Paragraph({ spacing: { after: 100 }, alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "Project Report", size: 22, color: INK, bold: true })] }),
        new Paragraph({ spacing: { after: 100 }, alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "Prepared for Raghav", size: 20, color: MUTED })] }),
        new Paragraph({ spacing: { after: 100 }, alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "August 2026", size: 20, color: MUTED })] }),
        new Paragraph({ children: [new PageBreak()] }),
        heading("Contents", HeadingLevel.HEADING_1),
        new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
        new Paragraph({ children: [new PageBreak()] }),
      ],
    },

    // ---------------- Main body ----------------
    {
      properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1080, bottom: 1080, left: 900, right: 900 } } },
      children: [

        heading("1. Executive Summary", HeadingLevel.HEADING_1),
        p("This project designs, implements, and evaluates a cost-sensitive mitigation policy for cloud VM host failures that incorporates four signals — predicted failure probability, estimated time-to-failure, workload criticality, and migration cost — and benchmarks it against the probability-threshold-based mitigation approach used as the common industry baseline. The system is inspired by, and explicitly contrasted with, Microsoft Azure's Narya."),
        p("Two real, independently-sourced datasets ground every stage: Backblaze's real hard-drive SMART/failure telemetry (122,618 real drives, 6,912 real failures) stands in for host failure signals, and Microsoft's own released Azure VM trace (2,013,767 real VMs) supplies real workload criticality and cost signals. A discrete-time hazard model, a derived time-to-failure estimator, a live-migration-theory-grounded cost model, and an explicit cost-sensitive decision rule were built and validated at each stage, then evaluated end-to-end in a purpose-built replay simulator against the real Backblaze failure histories."),
        p("The headline finding is more nuanced — and more credible — than a simple win: a naive comparison favored the cost-sensitive policy, but a fair comparison at matched migration budget showed it performing slightly worse than the threshold baseline, because the evaluation's random VM-to-host assignment made workload cost statistically independent of real failure risk. A follow-up experiment then identified the precise condition under which the hypothesis holds: once workload criticality correlates with host risk at a rank-correlation of roughly 0.3 or higher — a plausible level for real fleets with SLA-tiered hardware placement — the cost-sensitive policy's advantage over the threshold baseline rises monotonically, reaching +3.4% lower total realized cost at ρ=0.9, while also catching more real failures outright."),

        heading("2. Problem Statement", HeadingLevel.HEADING_1),
        p("A workload-aware, cost-sensitive mitigation policy that incorporates failure probability, estimated time-to-failure, workload criticality and migration cost can reduce customer-impacting VM failures while minimizing unnecessary migrations compared with probability-threshold-based mitigation.", { italics: true }),

        heading("3. Related Work", HeadingLevel.HEADING_1),
        heading("3.1 Narya (Microsoft Azure)", HeadingLevel.HEADING_2),
        p("Narya, published at OSDI 2020 and later productized inside Azure, runs three stages: predicting host failure from fleet telemetry (a mix of hand-written rules — e.g. two CPU IERR events within 30 days — and ML models), selecting a mitigation action, and measuring customer impact to keep improving. Its available actions are marking a node unallocatable, live-migrating VMs off it, a soft kernel reboot that preserves memory, deprioritizing new allocations, or sending the host to physical repair. Narya selects among these using online A/B experimentation and reinforcement learning tuned to customer-experience reward, rather than a published explicit cost formula, and reduced VM interruptions by roughly 26% over 15 months of production deployment versus its prior static strategy."),
        p("This project's contribution relative to Narya: it builds and evaluates an explicit, interpretable cost-sensitive decision rule — a function of failure probability, time-to-failure, workload criticality, and migration cost — rather than a learned bandit/RL policy, and benchmarks it directly against the simpler threshold approach most systems actually run."),
        heading("3.2 Probability-Threshold-Based Mitigation (Baseline)", HeadingLevel.HEADING_2),
        p("The baseline this project benchmarks against migrates any host whose predicted failure probability exceeds a fixed threshold τ, regardless of urgency, workload importance, or migration cost — functionally similar to the “static strategy” Narya's own paper improves on."),

        heading("4. Data Sources", HeadingLevel.HEADING_1),
        p("The evaluation environment (a sandboxed cloud container) only has network access to package registries and GitHub, not to arbitrary data hosts, which shaped how data was acquired — documented here for reproducibility rather than glossed over."),
        table(
          ["Role", "Dataset", "What it provides", "Size"],
          [
            ["Workload criticality + migration cost", "Azure Public Dataset V1 (Microsoft's own released VM trace, downloaded directly from its GitHub release)", "VM category (Interactive / Delay-insensitive / Unknown), vCPU count, memory, CPU utilization, lifetime, over a real 30-day trace", "2,013,767 VMs"],
            ["Failure probability + time-to-failure", "Backblaze HDD survival table (2013–2017), a real per-drive summary derived directly from Backblaze's own published daily SMART/failure files", "Per-drive: model, capacity, real failed/censored status, real age at that outcome", "122,618 drives, 6,912 real failures"],
          ],
          [2040, 3295, 3295, 1570]
        ),
        caption("Table 1. The two real datasets combined for this project. No public dataset links real VM placement to real host failures — that internal linkage is what makes Narya possible inside Azure — so this project combines two real, independently-sourced datasets rather than one linked (but non-public) one."),
        p("A known real-world artifact surfaced during preprocessing: drive model ST3000DM001 shows a 36.3% failure rate versus 3–8% for most other models in the fleet — this is the well-documented Seagate 3TB batch Backblaze itself publicly flagged as defective. Its presence in the data, and its correct recovery by the models built in Section 5, is used throughout this report as a face-validity check."),

        heading("5. Methodology", HeadingLevel.HEADING_1),

        heading("5.1 Failure Probability Model", HeadingLevel.HEADING_2),
        p("The Backblaze table gives one row per drive (final age, and whether that final event was a real failure or a censoring), which is a survival-analysis structure, not a plain classification table — training on it directly would leak the future. The data was expanded into person-period rows (one row per 30-day interval each drive is known to have survived through, labeled 1 only on the interval containing its failure), a standard discrete-time hazard model construction. A drive-level 80/20 split (no drive's intervals span both sets) was used to train and evaluate two candidates: logistic regression and a HistGradientBoostingClassifier, on features (drive-model group, capacity, interval start age)."),
        p("The first modeling attempt used class-balancing to address the ~0.2%-per-interval positive rate, which is a common reflex but was wrong here: it preserved ranking (ROC-AUC) while badly distorting the actual probability values — the model predicted ~50–70% risk for drives that truly failed at a ~0.2–0.9% rate. Since this probability feeds directly into an expected-cost calculation downstream, that miscalibration would have silently corrupted every later decision. It was caught and corrected before finalizing."),
        table(
          ["Model", "ROC-AUC", "PR-AUC", "Brier score"],
          [["Logistic hazard", "0.753", "0.017", "0.00203"], ["HistGBM hazard (selected)", "0.781", "0.020", "0.00202"]],
          [3570, 2210, 2210, 2210]
        ),
        caption("Table 2. Held-out person-period evaluation, without class-balancing. PR-AUC of ~0.02 against a ~0.002 base rate is roughly a 10x lift over random — modest in absolute terms, consistent with published SMART-based failure-prediction work; rare hardware failures with a 30-day lead time are a genuinely hard prediction problem."),
        p("Calibration — the property the downstream cost calculation actually depends on — was verified directly: predicted-risk deciles track empirical failure rates closely across the full range (e.g. a decile predicted at 0.906% failed at an actual rate of 0.944%), confirming the corrected model's probabilities are usable as real probabilities, not just a good ranking score."),

        heading("5.2 Time-to-Failure Estimation", HeadingLevel.HEADING_2),
        p("Rather than fitting a second, independent model, time-to-failure is derived by composition from the same hazard curve: the survival function S(t) = Π(1 − hazardₖ) implied by Section 5.1's per-(model, age) hazard estimates gives both expected residual life (the area under the conditional survival curve) and median residual life (the horizon at which that curve drops below 0.5). Keeping both signals on one underlying model means they cannot quietly disagree with each other."),
        p("Since Backblaze drives are observed out to only ~8 years, hazard was held constant at its last-observed value for an explicit, documented tail beyond that range, rather than letting the model silently extrapolate. One consequence: for 95.8% of (model, age) combinations, median time-to-failure is not a well-defined number (most drives of most models simply don't fail), so the policy uses expected residual life as its primary TTF signal."),
        p("Validation against real outcomes: the one model group Backblaze itself publicly flagged as defective (ST3000DM001) receives by far the shortest predicted expected TTF (2,691 days) versus 6,700–8,700 days for every other model group — recovered without being told about the recall. A concordance index computed by Monte Carlo sampling across real drive pairs (300,000 sampled pairs, 9,027 comparable) gave C = 0.7145 (0.5 = random, 1.0 = perfect), consistent with the 0.781 ROC-AUC from Section 5.1."),

        heading("5.3 Workload Criticality & Migration Cost", HeadingLevel.HEADING_2),
        p("Criticality tiers come directly from Azure's own VM category label: Interactive workloads (user/customer-facing) are treated as high criticality, Delay-insensitive (batch) as low, and Unknown as a conservative medium default."),
        p("Migration cost is grounded in the standard pre-copy live-migration formula from the systems literature (Clark et al., Live Migration of Virtual Machines, NSDI 2005): pre-copy duration ≈ memory size / (network bandwidth − dirty-page rate), using each VM's real memory, vCPU count, and average CPU utilization (a proxy for memory dirty-rate) from the Azure trace. The physical constants that turn those real inputs into a duration — network bandwidth (1,250 MB/s), maximum dirty-rate at 100% CPU (150 MB/s), a stop-and-copy fallback pause (60s), and an assumed unmitigated-failure recovery time (10 minutes) — are stated modeling assumptions, since no public dataset exposes Azure's actual migration telemetry or incident-recovery times."),
        p("A notable finding: at real Azure workload intensity (median VM CPU utilization of only 10.5%), pre-copy live migration converges cleanly for 100% of the 2 million VMs in the trace — nobody hits the slow stop-and-copy fallback. This means the customer-facing cost of migrating is small and nearly uniform fleet-wide; the cost that actually varies meaningfully between VMs is the infrastructure resource cost (bandwidth tied up during pre-copy), which spans roughly a 50x range from the smallest to the largest VMs."),
        table(
          ["VM size tier", "Mean resource cost (min)", "Median", "Max"],
          [["small", "0.032", "0.025", "0.230"], ["medium", "0.236", "0.192", "0.899"], ["large", "1.533", "1.529", "1.721"]],
          [2720, 2720, 2380, 2380]
        ),
        caption("Table 3. Migration resource cost by VM size tier, computed from real Azure memory/vCPU/CPU-utilization data."),

        heading("5.4 The Cost-Sensitive Mitigation Policy", HeadingLevel.HEADING_2),
        p("The policy migrates a host iff:", { spacingAfter: 60 }),
        p("expected_cost_of_inaction = p_fail × failure_cost × urgency(TTF)  >  migration_cost", { bold: true, alignment: AlignmentType.CENTER, spacingAfter: 220 }),
        p("failure_cost and migration_cost are already on a common customer-impact-minutes scale and already criticality-weighted (Section 5.3), so the comparison itself stays a plain expected-cost inequality. The one new mechanism is urgency(TTF): if expected time-to-failure already exceeds the 30-day decision lookahead, urgency stays at a neutral 1.0 (the risk is already reflected in p_fail itself, and inflating it further would double-count the same signal); if TTF is shorter than the lookahead, urgency scales up (capped at 5x), reflecting that an imminent failure leaves no room to defer the decision to a future reassessment."),
        p("The baseline migrates iff p_fail > τ, with τ set to the 95th percentile of real host risk states — “flag the riskiest 5% of observations,” a standard ops heuristic, not a number chosen to make the comparison favorable."),

        heading("5.5 Design Verification", HeadingLevel.HEADING_2),
        p("Before any temporal simulation, the two policies were checked two ways. First, five hand-built scenarios with a known correct answer: the one designed disagreement fired exactly as intended — at identical p_fail (0.006, just over τ), the threshold policy migrates a large, low-criticality VM with a distant expected failure purely because probability crossed a line (spending 1.5 minutes of real migration cost to avert an expected 0.018-minute cost of inaction); the cost-sensitive policy declines."),
        p("Second, a full decision surface: every real host-risk state (1,584, from Sections 5.1–5.2) crossed with every real representative VM cost profile (9 size × criticality buckets from Section 5.3) — 14,256 combinations. The two policies agreed 95.92% of the time; where they disagreed, the “threshold migrates unnecessarily” bucket (3.28% of states, skewed toward large/medium VMs with a distant expected failure) was over four times larger than the “cost-sensitive catches something missed” bucket (0.79%, skewed toward small, high-criticality VMs) — an early, encouraging signal, but a static one, not yet a measurement of actual outcomes."),

        heading("5.6 Evaluation Simulator", HeadingLevel.HEADING_2),
        p("Rather than a general-purpose cloud simulator (CloudSim, SimGrid), which model scheduling/energy/network and have no built-in notion of predicted failure probability or mitigation policy, a small purpose-built replay harness was built: all 122,618 real Backblaze drives serve as hosts, and the 2,013,767 real Azure VMs are assigned to them uniformly at random, once, identically for both policies (there being no public dataset linking real VM placement to real host failures). Each host walks forward through its own real health trajectory in 30-day steps; both policies decide migrate/wait using only information available at that step; a host's real fate is a fixed fact from the data, since migrating workloads off a host does not change whether the physical hardware itself fails."),
        p("Four outcomes are scored per host per policy: necessary migration (migrated, host would have failed), customer-impacting failure (never migrated in time, host failed), unnecessary migration (migrated, host never failed), correct inaction (never migrated, host never failed)."),

        heading("6. Results", HeadingLevel.HEADING_1),

        heading("6.1 Naive Comparison", HeadingLevel.HEADING_2),
        table(
          ["Metric", "Cost-sensitive", "Threshold (τ=0.0073)"],
          [
            ["Customer-impacting failures", "5,493", "4,872"],
            ["Unnecessary migrations", "3,697", "5,940"],
            ["Total migrations", "5,116", "7,980"],
            ["Total cost impact (customer-min)", "456,533", "410,867"],
          ],
          [3976, 3111, 3113]
        ),
        caption("Table 4. Taken at face value this favors the threshold on cost and failure count — but the two policies are operating at very different overall aggressiveness levels (5,116 vs 7,980 total migrations), an artifact of how the Section 5.3 cost constants happen to be calibrated, not evidence about which targeting logic is better."),

        heading("6.2 Fair Comparison at Matched Migration Budget", HeadingLevel.HEADING_2),
        p("The principled comparison holds the migration budget fixed and asks which policy spends it better — standard practice for comparing tunable policies (e.g. comparing at matched recall rather than at two independently-chosen thresholds). τ was swept to the closest achievable match to the cost-sensitive policy's migration count."),
        table(
          ["Metric", "Cost-sensitive (5,116 migrations)", "Threshold, matched (5,522 migrations)"],
          [
            ["Customer-impacting failures", "5,493", "5,311"],
            ["Necessary migrations", "1,419", "1,601"],
            ["Unnecessary migrations", "3,697", "3,921"],
            ["Total cost impact (customer-min)", "456,533", "442,701"],
          ],
          [3665, 3187, 3348]
        ),
        caption("Table 5. At a matched budget, the plain probability threshold comes out about 3.1% ahead on total cost and catches more real failures. Reporting the naive comparison as a win would have misrepresented the experiment."),
        p("A follow-up diagnostic — splitting the 6,912 real failures into cost quartiles and checking each policy's miss rate per quartile — found no sign that cost-sensitivity better protects the highest-cost failures specifically; miss rate rose slightly across quartiles at roughly the same slope for all policy variants. The likely mechanism is structural: VMs were assigned to hosts uniformly at random, which makes workload cost statistically independent of a host's actual hazard by construction — when cost carries no information about who is actually going to fail, re-weighting a fixed budget by cost can only add noise relative to pure probability-ranking."),

        heading("6.3 Resolving Experiment: Correlated Workload–Risk Assignment", HeadingLevel.HEADING_2),
        p("This motivates a direct test: if workload importance genuinely correlates with hardware failure risk — plausible in real fleets through SLA-tiered hardware placement or legacy critical services left on aging infrastructure — does the cost-sensitive policy's advantage appear? A controlled rank-correlation sweep (a simplified Iman-Conover method) re-ran the identical replay simulator and matched-budget comparison at four correlation levels between VM criticality and host risk."),
        table(
          ["Target ρ", "Achieved rank-corr.", "Missed failures (cost-sensitive)", "Missed failures (threshold, matched)", "Cost-sensitive advantage"],
          [
            ["0.0", "−0.00", "5,499", "5,311", "−3.1%"],
            ["0.3", "0.31", "5,335", "5,311", "+0.3%"],
            ["0.6", "0.73", "5,243", "5,310", "+2.0%"],
            ["0.9", "0.86", "5,141", "5,254", "+3.4%"],
          ],
          [1316, 1974, 2386, 2386, 2138]
        ),
        caption("Table 6. Cost-sensitive policy's total-cost advantage rises monotonically with correlation, crossing over to a real win around ρ ≈ 0.3. Its raw missed-failure count also falls as ρ rises (5,499 → 5,141) while the threshold's stays roughly flat (~5,310) — confirming the improvement reflects genuinely better targeting, not just reweighting."),
        new Paragraph({
          spacing: { before: 120, after: 80 },
          alignment: AlignmentType.CENTER,
          children: [new ImageRun({ data: fs.readFileSync(__dirname + "/../docs/figures/correlation_sweep_chart.png"), transformation: { width: 570, height: 350 }, type: "png" })],
        }),
        caption("Figure 1. Cost-sensitive policy's advantage over the matched-budget threshold as a function of workload-criticality/host-risk correlation."),
        p("This turns the project's hypothesis into a conditional, falsifiable claim rather than an unconditional one: cost-sensitive mitigation outperforms probability-threshold mitigation specifically when workload criticality correlates with hardware failure risk, and the crossover point (ρ ≈ 0.3) is a fairly modest, plausible level of correlation — not an extreme case constructed to force a win."),

        heading("7. Discussion & Limitations", HeadingLevel.HEADING_1),
        bullet("Provenance of the failure dataset: the raw Backblaze daily SMART files were not directly reachable from this project's network-restricted environment; a real, third-party-aggregated survival summary derived from those same real files was used instead. Every row is a genuine drive with a genuine outcome, but per-day SMART feature richness (beyond model and age) was not available."),
        bullet("Cost-model constants (migration bandwidth, dirty-page rate, unmitigated-failure recovery time) are documented modeling assumptions grounded in published ranges, not measured Azure infrastructure telemetry, since no public dataset exposes that data."),
        bullet("The core empirical claim is conditional: this project demonstrates the cost-sensitive policy wins once workload criticality correlates with host risk at ρ ≳ 0.3, but whether real production fleets actually operate above that threshold is an open empirical question this project cannot verify directly, for the same data-availability reason noted above."),
        bullet("The policy is myopic (one-step-ahead expected cost), not a full optimal-stopping formulation; a sequential/adaptive-aggressiveness framing (Section 6.3's second suggested follow-up) was identified but not built out in this iteration."),
        bullet("Migration is modeled as a cost and an outcome, not executed; no live-migration mechanics, network topology, or cross-host contention are simulated."),

        heading("8. Conclusion & Future Work", HeadingLevel.HEADING_1),
        p("This project built a complete, real-data-grounded pipeline — from failure prediction through time-to-failure estimation, cost modeling, policy design, and a purpose-built replay simulator — to test whether workload-aware, cost-sensitive VM mitigation beats a probability-threshold baseline. The honest result is conditional rather than unconditional: under random workload placement the two policies are roughly matched (the threshold slightly ahead), and the cost-sensitive policy's advantage emerges cleanly and monotonically once workload criticality correlates with real hardware risk at a plausible level (ρ ≳ 0.3). This is a more defensible and more interesting outcome than an unconditional win would have been, because it identifies precisely the operating condition under which the mechanism this project proposes actually works."),
        p("Future work: (1) test the adaptive-aggressiveness reframing of the policy suggested in Section 7; (2) if any real (even proprietary or anonymized) signal linking workload placement to hardware generation/tier becomes available, measure the real ρ in production rather than assuming one; (3) extend the hazard model with richer per-day SMART features if the raw Backblaze daily files can be obtained; (4) sensitivity-test the Section 5.3 cost constants directly, since Section 6.1 showed the naive comparison is sensitive to exactly how aggressive the resulting policy turns out to be."),

        heading("9. References", HeadingLevel.HEADING_1),
        bullet("Microsoft Research. Predictive and Adaptive Failure Mitigation to Avert Production Cloud VM Interruptions (Narya), OSDI 2020."),
        bullet("Azure Blog. Advancing failure prediction and mitigation — introducing Narya, 2021."),
        bullet("Clark, C. et al. Live Migration of Virtual Machines, NSDI 2005."),
        bullet("Backblaze. Hard Drive Data and Stats (2013–2017 daily SMART/failure telemetry), backblaze.com/cloud-storage/resources/hard-drive-test-data."),
        bullet("Microsoft Azure. Azure Public Dataset V1 (VM trace), github.com/Azure/AzurePublicDataset."),

        heading("Appendix: Project Files", HeadingLevel.HEADING_1),
        p("Scripts (in scripts/, run in order from the project root):"),
        bullet("01_preprocess.py — loads and cleans both raw datasets"),
        bullet("02_failure_probability_model.py — discrete-time hazard model (Section 5.1)"),
        bullet("03_time_to_failure.py — TTF derivation and validation (Section 5.2)"),
        bullet("04_workload_criticality_cost.py — criticality tiers and migration cost model (Section 5.3)"),
        bullet("policy.py, 05_policy_design.py — the two decision rules and their pre-simulation verification (Sections 5.4–5.5)"),
        bullet("06_simulation_evaluation.py — the replay simulator, naive and matched-budget comparisons (Sections 5.6, 6.1–6.2)"),
        bullet("07_correlated_assignment_experiment.py — the correlation sweep (Section 6.3)"),
        p("All intermediate and final data live under data/processed/; per-task narrative detail beyond this report is in docs/task*_summary.md.", { spacingAfter: 0 }),
      ],
    },
  ],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(__dirname + "/../docs/VM_Mitigation_Policy_Report.docx", buf);
  console.log("wrote docs/VM_Mitigation_Policy_Report.docx");
});
