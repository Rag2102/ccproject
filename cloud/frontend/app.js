// Static-frontend logic for the AWS deployment. The Render/Flask deployment
// (webapp/templates/index.html) renders this same reference data server-side
// via Jinja; this page has no server, so it fetches the identical JSON from
// GET /api/meta (Lambda, via core.get_meta() -- see webapp/core.py) and
// builds the DOM itself. API_BASE comes from config.js, which Terraform
// generates with the real API Gateway URL at deploy time (cloud/infra).

let META = null;

function fmtMetric(value) {
  if (typeof value !== "number") return value;
  return Math.abs(value) < 5 ? value.toFixed(4) : value.toFixed(0);
}

function populateSelect(id, values) {
  const el = document.getElementById(id);
  el.innerHTML = values.map(v => `<option value="${v}">${v}</option>`).join("");
}

function renderHeadlineTable(headline) {
  const tbody = document.querySelector("#headline-table tbody");
  tbody.innerHTML = Object.entries(headline).map(([metric, row]) => `
    <tr>
      <td>${metric.replace(/_/g, " ")}</td>
      <td>${fmtMetric(row.cost_sensitive)}</td>
      <td>${fmtMetric(row.threshold)}</td>
    </tr>`).join("");
}

function renderComparisonTable(comparison) {
  const tbody = document.querySelector("#comparison-table tbody");
  tbody.innerHTML = comparison.map(row => `
    <tr>
      <td>${row.model}</td>
      <td>${Number(row.roc_auc).toFixed(4)}</td>
      <td>${Number(row.pr_auc).toFixed(4)}</td>
      <td>${Number(row.brier).toFixed(5)}</td>
      <td>${Number(row.ece).toFixed(5)}</td>
    </tr>`).join("");
}

async function loadMeta() {
  const res = await fetch(`${window.API_BASE}/api/meta`);
  if (!res.ok) throw new Error(`GET /api/meta failed: HTTP ${res.status}`);
  META = await res.json();

  populateSelect("model_grp", META.model_groups);
  populateSelect("criticality_tier", META.criticality_tiers);
  populateSelect("size_tier", META.size_tiers);

  const ageInput = document.getElementById("age_days");
  ageInput.max = META.max_age_days;
  ageInput.step = META.bin_days;

  document.getElementById("th-tau").textContent = META.tau_default;
  document.getElementById("stat-pfail-label").textContent = `P(fail within ${META.lookahead_days}d)`;

  renderHeadlineTable(META.headline);
  renderComparisonTable(META.comparison);

  const btn = document.getElementById("run-btn");
  btn.disabled = false;
  btn.querySelector(".btn-label").textContent = "Run live prediction";
}

const ageInput = document.getElementById('age_days');
const ageVal = document.getElementById('age_val');
function updateAgeLabel() { ageVal.textContent = ageInput.value + ' days (~' + (ageInput.value/365).toFixed(1) + ' yr)'; }
ageInput.addEventListener('input', updateAgeLabel);
updateAgeLabel();

async function runPredict() {
  const which_model = document.querySelector('input[name=which_model]:checked').value;
  const payload = {
    model_grp: document.getElementById('model_grp').value,
    age_days: parseFloat(ageInput.value),
    criticality_tier: document.getElementById('criticality_tier').value,
    size_tier: document.getElementById('size_tier').value,
    which_model: which_model,
  };
  const btn = document.getElementById('run-btn');
  const label = btn.querySelector('.btn-label');
  btn.disabled = true; btn.classList.add('loading'); label.textContent = 'Running model...';
  try {
    const res = await fetch(`${window.API_BASE}/api/predict`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    document.getElementById('result-placeholder').style.display = 'none';
    const resultEl = document.getElementById('result');
    resultEl.style.display = 'none';
    void resultEl.offsetWidth; // restart fade-in animation on every run
    resultEl.style.display = 'block';

    document.getElementById('stat-pfail').textContent = (data.p_fail_within_window*100).toFixed(3) + '%';
    document.getElementById('stat-ttf').textContent = data.expected_ttf_days;
    document.getElementById('stat-mediattf').textContent = data.median_ttf_days ?? 'n/a (beyond horizon)';

    const csBadge = document.getElementById('cs-badge');
    csBadge.innerHTML = '<span class="badge ' + (data.cost_sensitive.migrate ? 'migrate">MIGRATE' : 'wait">WAIT') + '</span>';
    document.getElementById('cs-cost').textContent = data.cost_sensitive.expected_cost_of_inaction + ' impact-min';
    document.getElementById('cs-migcost').textContent = data.cost_sensitive.migration_cost + ' impact-min';
    document.getElementById('cs-urgency').textContent = 'x' + data.cost_sensitive.urgency_weight;

    const thBadge = document.getElementById('th-badge');
    thBadge.innerHTML = '<span class="badge ' + (data.threshold.migrate ? 'migrate">MIGRATE' : 'wait">WAIT') + '</span>';

    let note = 'Model used: ' + data.model_used + '. Migration: ' +
      (data.costs.precopy_converges ? 'pre-copy converges' : 'forced stop-and-copy fallback') +
      ' (' + data.costs.migration_time_s + 's, blackout ' + data.costs.migration_blackout_s + 's).';
    if (data.mc_dropout_std !== null && data.mc_dropout_std !== undefined) {
      note += ' MC-dropout uncertainty (std across 15 stochastic passes): ' + data.mc_dropout_std.toFixed(4) +
              ' -- this model is NumPy-only and less well-calibrated than the HistGBM default; see task11_summary.md.';
    }
    document.getElementById('model-note').textContent = note;
  } catch (e) {
    alert('Prediction failed: ' + e + '\n\nIs the API_BASE in config.js correct, and is the Lambda deployed?');
  } finally {
    btn.disabled = false; btn.classList.remove('loading'); label.textContent = 'Run live prediction';
  }
}

loadMeta().catch(e => {
  document.getElementById('run-btn').querySelector('.btn-label').textContent = 'Failed to load (see console)';
  console.error('Failed to load /api/meta:', e);
  alert('Could not load reference data from the API: ' + e + '\n\nCheck that config.js has the correct API_BASE.');
});
