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
const CODE_FILL = "F4F3F1";

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

function code(text) {
  const lines = text.split("\n");
  return new Paragraph({
    shading: { type: ShadingType.CLEAR, fill: CODE_FILL },
    spacing: { before: 120, after: 200 },
    indent: { left: convertInchesToTwip(0.2), right: convertInchesToTwip(0.2) },
    children: lines.map((line, i) => new TextRun({
      text: line, font: "Consolas", size: 19, color: INK, break: i === 0 ? 0 : 1,
    })),
  });
}

function cell(text, { header = false, width, align = AlignmentType.LEFT, mono = false } = {}) {
  return new TableCell({
    width: width ? { size: width, type: WidthType.DXA } : undefined,
    shading: header ? { type: ShadingType.CLEAR, fill: HEADER_FILL } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({
      alignment: align,
      children: [new TextRun({ text: String(text), bold: header, size: 20, color: INK, font: mono ? "Consolas" : undefined })],
    })],
  });
}

function table(headerRow, rows, colWidths, monoCols = []) {
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
        children: r.map((v, i) => cell(v, { width: colWidths[i], align: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER, mono: monoCols.includes(i) })),
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
          children: [new TextRun({ text: "Inside the Live Model", bold: true, size: 44, color: INK })] }),
        new Paragraph({ spacing: { after: 600 }, alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "A Technical Walkthrough of the Prediction Engine (webapp/core.py)", bold: true, size: 32, color: INK })] }),
        new Paragraph({ spacing: { after: 200 }, alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "How one shared module turns a drive model, an age, and a workload profile",
            size: 24, color: MUTED })] }),
        new Paragraph({ spacing: { after: 1200 }, alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "into a real, live migrate/wait decision -- for both deployments",
            size: 24, color: MUTED })] }),
        new Paragraph({ spacing: { after: 100 }, alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "Technical Companion Report", size: 22, color: INK, bold: true })] }),
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

        heading("1. What This Document Covers", HeadingLevel.HEADING_1),
        p("The main project report (VM_Mitigation_Policy_Report.docx) explains the research: what was tested, on what data, and what was found. This document is narrower and more mechanical -- it explains how the actual running code behind the live demo works, line by line, so the model isn't a black box when explaining it to a presenter."),
        p("Every prediction the live demo shows -- on the Render deployment and the AWS deployment alike -- runs through exactly one module: webapp/core.py. Neither webapp/app.py (the Flask server) nor cloud/api/lambda_function.py (the AWS Lambda handler) contains any modeling or decision logic of its own; they are thin request/response wrappers that both call the same two functions in core.py: get_meta() and run_predict(). This is a deliberate design choice, not an accident -- it guarantees the two deployments can never silently drift apart in what they compute, and it means everything below applies identically to both."),

        heading("2. What Loads Once, at Startup", HeadingLevel.HEADING_1),
        p("core.py does its expensive work exactly once per process -- once per Lambda container on a cold start, once at process start for the traditional Flask server -- not on every request:"),
        table(
          ["Artifact", "File", "What it is"],
          [
            ["HGB_BUNDLE", "models/failure_probability_model.joblib", "The trained, calibrated HistGradientBoostingClassifier hazard model, plus its feature list and training categories"],
            ["GQAT_BUNDLE", "models/gqat_net_numpy_model.joblib", "The hand-written NumPy attention model, its feature scaler, isotonic calibrator, and per-model-group lookup tables"],
            ["HAZARD_LOOKUP", "data/processed/hazard_lookup_table.csv", "Precomputed hazard/p_fail by (model group, age bin) -- used only to compute the live threshold τ, not to answer predictions"],
            ["COMPARISON, HEADLINE, CORR_SWEEP", "data/processed/*.csv", "The project's precomputed, already-validated research findings, served as-is for the “Real findings” panel"],
            ["SIZE_TIER_PROFILE", "data/processed/size_tier_profile.json", "Real median memory/vCPU/CPU-utilization per VM size tier, extracted once from the 198MB Azure cost table so the deployed app never has to load it"],
          ],
          [2400, 2800, 4000]
        ),
        caption("Table 1. Everything loaded once at process start. TAU_DEFAULT (the threshold policy's cutoff) is also computed here, live, as the 95th percentile of HAZARD_LOOKUP's real p_fail values -- not hardcoded."),
        p("Two module-level constants worth knowing because they show up everywhere below: BIN_DAYS = 30 (the width of one hazard time-step, matching how the Backblaze data was binned in Section 5.1 of the main report) and LOOKAHEAD_DAYS = 30 (the decision window -- “will this fail in the next 30 days”)."),

        heading("3. Step 1 — Turning (Drive Model, Age) Into a Hazard Curve", HeadingLevel.HEADING_1),
        p("This is the one step with two different implementations, selected by the which_model field in the request -- everything after this step is identical regardless of which model produced the curve."),

        heading("3.1 Calibrated HistGBM (the default)", HeadingLevel.HEADING_2),
        p("hazard_curve_histgbm() builds a small synthetic table: one row per 30-day age bin from 0 out to MAX_AGE_DAYS (3,000 days) plus 200 extra tail bins, holding the requested drive model and its real median capacity fixed and varying only age. That table is fed straight into the trained model's predict_proba() -- this is a genuine forward pass through the trained HistGBM on every request, not a cache lookup. Beyond the last real bin, hazard is held constant at its last computed value (the same documented “constant-hazard tail” convention used when the model was built -- see Section 5.2 of the main report)."),
        code("bins = _bin_grid()  # 0, 30, 60, ... out past 3000 days\ngrid = DataFrame({model_grp, capacity_tb, bin_start_days: bins})\nhaz = HGB_BUNDLE[\"model\"].predict_proba(grid[features])[:, 1]\nhaz[n_real:] = haz[n_real - 1]   # constant tail beyond real data"),

        heading("3.2 GQAT-Net-inspired (NumPy, the “try the deep model” option)", HeadingLevel.HEADING_2),
        p("hazard_curve_gqat() does more work per request, because the model it calls expects 11 engineered features rather than the 3 raw ones the tree model uses (see Section “Adapting the data” in docs/task11_summary.md for why). For every age bin in the grid, this function computes: bin index, age in years, log1p(age), a normalized age² term, an ordinal code for the drive model, that model's historical hazard rate, an is-new-drive flag, a capacity×age interaction, and the drive's capacity deviation from its model's median. Those 11 columns are scaled with the model's fitted StandardScaler, passed through the hand-written network's predict_proba(), and then run through an isotonic regression calibrator -- the same two-stage “raw prediction, then recalibrate” pattern used for the HistGBM model, because the project's own finding (Section 5.1 of the main report) is that an uncalibrated probability is dangerous to plug into a cost formula."),
        p("This path also computes something the HistGBM path doesn't: MC-dropout uncertainty. It re-runs a small slice of the request (at most 60 rows, near the requested age) through the network 15 times with dropout left active, and reports the standard deviation across those 15 stochastic passes as mc_dropout_std -- a rough, honest signal of how uncertain this specific prediction is, surfaced directly in the demo's result note rather than hidden."),
        code("Xs = scaler.transform(engineered_11_features)\np_raw = GQAT_BUNDLE[\"model\"].predict_proba(Xs)\nhaz = GQAT_BUNDLE[\"isotonic\"].predict(p_raw)      # calibration fix\nmc_mean, mc_std = GQAT_BUNDLE[\"model\"].predict_proba_mc(Xs[:60], n_iter=15)"),
        p("Both paths return the same shape -- (bins, hazard array, optional mc_std) -- which is what lets everything downstream stay model-agnostic."),

        heading("4. Step 2 — From Hazard Curve to Time-to-Failure", HeadingLevel.HEADING_1),
        p("survival_and_ttf() is pure math over whichever hazard array Step 1 produced -- it never touches a model again. It implements exactly the composition described in Section 5.2 of the main report:"),
        bullet("Slice the hazard array starting at the drive's current age (start_idx), then form the conditional survival curve by cumulative product: S(t) = Π(1 − hazard_k) for every bin from now forward, prefixed with S(0) = 1.0."),
        bullet("Expected residual TTF = the area under that survival curve, via trapezoidal integration over the 30-day bins."),
        bullet("Median residual TTF = the first bin where survival drops below 0.5, linearly interpolated between the two surrounding bins for a smooth day count -- or None if the curve never crosses 0.5 within the tail (the demo shows this honestly as “n/a (beyond horizon)” rather than a misleading number, matching the finding in Section 5.2 that 95.8% of real (model, age) combinations never see median TTF defined)."),
        bullet("p_fail_within_window (the number labeled “P(fail within 30d)” on the page) = 1 − the product of (1 − hazard) over just the next LOOKAHEAD_DAYS / BIN_DAYS bins -- a short, separate calculation from the residual-life integral, because “risk in the next 30 days” and “expected total remaining life” are different questions answered from the same curve."),
        code("surv = cumprod(1 - hazard[start_idx:])\nsurv_full = concat([1.0], surv)\nexpected_ttf = trapezoid(surv_full, t_days)\nmedian_ttf   = interpolate(first index where surv_full <= 0.5)\np_fail_window = 1 - prod(1 - hazard[start_idx : start_idx + n_steps])"),

        heading("5. Step 3 — Pricing the Migration and the Failure", HeadingLevel.HEADING_1),
        p("migration_and_failure_cost() is the live implementation of the Clark et al. pre-copy formula described in Section 5.3 of the main report, run against the chosen VM size tier's real median memory/vCPU/CPU-utilization (from SIZE_TIER_PROFILE):"),
        bullet("Convert the size tier's average CPU utilization into a memory dirty-rate (as a fraction of a 150 MB/s ceiling at 100% CPU)."),
        bullet("Check convergence: pre-copy only works if that dirty-rate is comfortably below the 1,250 MB/s migration link's bandwidth (a 90% margin is required). At real Azure workload intensity this almost always holds -- see Section 5.3's fleet-wide finding that 100% of VMs converge."),
        bullet("If it converges: migration_time_s = memory (MB) / (bandwidth − dirty-rate), and the customer-visible blackout is a fixed 1 second (the final stop-and-copy handoff). If it doesn't: fall back to a 60-second stop-and-copy pause for both the duration and the blackout."),
        bullet("Two costs are kept separate on purpose, in customer-impact-minutes: migration_resource_cost_min (the whole pre-copy duration -- doesn't interrupt the VM, but ties up bandwidth) and migration_customer_cost_min (just the blackout, weighted by the workload's criticality). failure_customer_cost_min (a fixed 10-minute unmitigated-outage assumption, criticality-weighted) is computed the same way."),
        code("dirty_rate = (avg_cpu/100) * 150\nconverges = dirty_rate < 0.9 * 1250\nmigration_time_s = memory_mb / (1250 - dirty_rate)   if converges else 60\nmigration_customer_cost_min = (blackout_s/60) * criticality_weight\nfailure_customer_cost_min   = 10 * criticality_weight"),

        heading("6. Step 4 — The Decision Layer", HeadingLevel.HEADING_1),
        p("Steps 1–3 hand three numbers -- p_fail_window, expected_ttf, and the two costs -- to scripts/policy.py, imported unchanged by core.py so the decision logic tested and validated in Sections 5.4–5.5 of the main report is exactly the code running live here, not a re-implementation."),
        p("Cost-sensitive policy: migrate iff p_fail × failure_cost × urgency(TTF)  >  migration_cost. The urgency term is the one piece of logic worth re-stating: if expected TTF already exceeds the 30-day lookahead, urgency stays at a neutral 1.0 (that risk is already priced into p_fail itself); if TTF is shorter than the lookahead, urgency scales up toward a 5x cap, because an imminent failure leaves less room to defer the decision to a future re-check."),
        p("Threshold baseline: migrate iff p_fail > τ, where τ = TAU_DEFAULT, computed once at startup as the 95th percentile of real host-risk states -- “flag the riskiest 5%,” nothing else enters this decision."),
        code("urgency = clip(30 / max(ttf_days, 1), 1.0, 5.0)\nexpected_cost_of_inaction = p_fail * failure_cost * urgency\ncost_sensitive_migrate = expected_cost_of_inaction > migration_cost\nthreshold_migrate      = p_fail > tau_default"),

        heading("7. Worked Example: One Full Prediction, Start to Finish", HeadingLevel.HEADING_1),
        p("To make the four steps concrete, here is a single real request traced through the actual running code -- the same inputs used to sanity-check the demo during development. Drive model HDS5C3030ALA630, age 900 days, workload criticality high, VM size tier large, Calibrated HistGBM.", { italics: true }),
        table(
          ["Quantity", "Value", "Where it came from"],
          [
            ["capacity_tb", "3.0", "This drive model's real median capacity"],
            ["start_idx", "30  (bin at day 900)", "age_days // BIN_DAYS"],
            ["hazard at start_idx", "0.000499", "Live HistGBM forward pass, this age bin"],
            ["p_fail_within_window", "0.0499%", "1 − (1 − 0.000499)  over 1 bin (30-day lookahead = 1 bin)"],
            ["expected_ttf_days", "7,312.4", "Trapezoidal integral of the survival curve from day 900 forward"],
            ["median_ttf_days", "n/a (beyond horizon)", "Survival curve never drops below 0.5 within the tail"],
            ["size tier profile (large)", "112 GB mem, 16 vCPU, 0.06% avg CPU", "Real Azure median for this size tier"],
            ["precopy_converges", "true", "Dirty-rate ≈ 0 MB/s, far below the 1,125 MB/s (90%) ceiling"],
            ["migration_time_s / blackout_s", "91.76s / 1.0s", "112 GB / (1250 − ~0) MB/s;  blackout is the fixed 1s case"],
            ["total_migration_cost_min", "1.546", "1.529 (resource) + 0.017 (customer, blackout × criticality 1.0)"],
            ["failure_customer_cost_min", "10.0", "10 min × criticality weight 1.0 (high)"],
            ["urgency_weight", "1.0", "expected TTF (7,312d) ≫ lookahead (30d) → neutral"],
            ["expected_cost_of_inaction", "0.00499", "0.000499 × 10.0 × 1.0"],
            ["cost-sensitive decision", "WAIT", "0.00499  is not >  1.546"],
            ["threshold decision (τ=0.00731)", "WAIT", "0.000499  is not >  0.00731"],
          ],
          [2900, 2700, 3600],
          [1]
        ),
        caption("Table 2. Both policies agree here -- a healthy drive, deep into its expected life, on a large VM where migrating would cost far more than the risk justifies. This is the common case (Section 5.5 of the main report found the two policies agree on 95.9% of real states); the interesting disagreements happen at higher hazard, shorter TTF, or smaller/more-critical VMs."),

        heading("8. The Request/Response Contract", HeadingLevel.HEADING_1),
        p("Both deployments expose exactly two operations, and both are direct pass-throughs to core.py:"),
        table(
          ["Function", "Called by", "Returns"],
          [
            ["get_meta()", "GET /  (Render, via Jinja) and GET /api/meta  (both deployments, JSON)", "Dropdown options, tau_default, the precomputed headline/comparison/correlation-sweep tables, and the age slider's bounds -- everything the page needs to render its controls and its “Real findings” panel"],
            ["run_predict(body)", "POST /api/predict  (both deployments, identical JSON contract)", "model_used, p_fail_within_window, expected_ttf_days, median_ttf_days, mc_dropout_std, the full costs object, and a cost_sensitive / threshold verdict pair -- exactly what the result panel and the “Save this result to disk” download populate from"],
          ],
          [2000, 3600, 3600]
        ),
        caption("Table 3. Because Flask's app.py and Lambda's lambda_function.py both call these same two functions with no logic of their own, a request built identically against either deployment's /api/predict returns byte-identical JSON."),

        heading("9. Why It's Built This Way", HeadingLevel.HEADING_1),
        bullet("Single source of truth: every number the live demo ever shows traces back to one module, so “why did it say WAIT here” always has exactly one place to look, and the Render and AWS deployments cannot silently diverge in behavior even as their infrastructure differs completely."),
        bullet("Genuinely live, not a lookup table: Section 3 above is a real forward pass through a trained model on every request -- the only precomputed data served as-is are the project's own already-validated research findings (the headline/comparison/correlation-sweep tables), which are clearly labeled as such in the UI rather than presented as live output."),
        bullet("Testable in isolation: because core.py has no Flask or AWS dependency baked in, tests/test_core.py exercises survival_and_ttf(), the cost model, and both policy functions directly against known-good values (including a locked-in regression value for a real payload) without needing a running server -- these tests run in the project's GitHub Actions CI on every push."),
        bullet("Numbers that are computed, not hardcoded, wherever a real answer exists: TAU_DEFAULT is derived live from the real hazard lookup table rather than typed in as a constant, and SIZE_TIER_PROFILE is extracted once from real Azure data rather than guessed."),

        heading("Appendix: File Map", HeadingLevel.HEADING_1),
        table(
          ["File", "Role"],
          [
            ["webapp/core.py", "Everything documented above -- the one shared inference/decision module"],
            ["scripts/policy.py", "The two decision functions (Section 6), imported unchanged by core.py"],
            ["webapp/app.py", "Flask entrypoint (Render) -- routes only, no logic"],
            ["cloud/api/lambda_function.py", "AWS Lambda entrypoint -- routes only, no logic"],
            ["models/failure_probability_model.joblib", "The trained, calibrated HistGBM hazard model"],
            ["models/gqat_net_numpy_model.joblib", "The hand-written NumPy attention model, scaler, and calibrator"],
            ["tests/test_core.py", "Unit tests against core.py directly, run in CI"],
          ],
          [3400, 6400]
        ),
        p("For the research behind these models -- how they were trained, validated, and what was found when the resulting policy was evaluated against real drive histories -- see VM_Mitigation_Policy_Report.docx.", { spacingAfter: 0 }),
      ],
    },
  ],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(__dirname + "/../docs/Core_Model_Technical_Report.docx", buf);
  console.log("wrote docs/Core_Model_Technical_Report.docx");
});
