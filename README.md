# A Workload-Aware, Cost-Sensitive Mitigation Policy for Cloud VM Failures

A project testing whether a cost-sensitive VM mitigation policy — one that weighs failure probability, estimated time-to-failure, workload criticality, and migration cost — reduces customer-impacting VM failures and unnecessary migrations better than a plain probability-threshold policy (the common baseline, and the strategy Microsoft's Narya explicitly improves on).

**Headline result:** under random workload placement the two policies come out roughly matched (the threshold slightly ahead at a fair, matched migration budget); the cost-sensitive policy's advantage emerges cleanly and monotonically once workload criticality correlates with real hardware risk at a plausible level (rank-correlation ρ ≳ 0.3), reaching +3.4% lower realized cost at ρ=0.9. Full writeup: [`docs/VM_Mitigation_Policy_Report.docx`](docs/VM_Mitigation_Policy_Report.docx).

## See it working: the live demo

```
pip install -r requirements.txt
cd webapp
python3 app.py
# open http://127.0.0.1:5000
```

A small Flask app: pick a real drive model, an age, a workload criticality, and a VM size, and it runs one of the
two trained failure-probability models **live** (your choice of the calibrated HistGBM from task 3, or the
from-scratch NumPy attention model from task 11), builds a survival curve, derives time-to-failure, prices a
real migration via the Clark et al. pre-copy formula, and shows what the cost-sensitive policy and the
threshold baseline each decide on those exact inputs -- side by side. It also displays the project's actual
validated headline results (the matched-budget comparison and the correlation-sweep chart) so the real
experimental findings are visible alongside the interactive part. This is genuine model inference each time you
click "run," not a lookup into a precomputed table.

Two notes on infrastructure-simulation tools, since this is exactly the kind of project people reach for
CloudSim or VMware to demo: neither is a fit here. CloudSim/SimGrid simulate datacenter *scheduling and
resource contention*; VMware is virtualization *infrastructure*. This project's actual deliverable is a
*decision policy* over three learned/derived signals (p_fail, TTF, cost) -- a lightweight web app that runs the
real trained models and the real decision functions demonstrates that far more directly than provisioning
either kind of heavyweight tool would. This mirrors `docs/project_scope.md`'s original reasoning for using a
purpose-built replay simulator instead of CloudSim/SimGrid for the *evaluation* itself (task 8) -- the same
"wrong tool for this job" reasoning applies even more strongly to a demo.

## A second deployment: real cloud architecture on AWS

The Render deployment above is one traditional server. `cloud/` holds a
second, more substantial deployment built specifically to demonstrate
cloud-native architecture: a static frontend on S3 + CloudFront, a
serverless JSON API on API Gateway + Lambda (container images, since
pandas/scikit-learn make zip-based Lambda painful), and -- the most
interesting piece -- the correlation-sweep experiment (task 9) reworked
from a single-seed local for-loop into 55 real, independent Lambda
invocations fanned out by a Step Functions Map state and combined by an
aggregator Lambda into a proper mean +/- std per correlation value.

Both deployments share the exact same prediction logic (`webapp/core.py`)
-- see `docs/cloud_architecture.md` for the full design and a diagram, and
`cloud/README.md` for the exact `terraform apply` / `docker build` / `aws
stepfunctions start-execution` commands to deploy it into your own AWS
account.

## Repository layout

```
scripts/    Pipeline, run in order (01 → 08); policy.py and build_report.js are imported/used by later steps
webapp/     The live demo (Flask) -- see "See it working" above
models/     Saved, ready-to-use models the webapp loads directly (no retraining needed to run the demo)
docs/       Per-stage write-ups (task*_summary.md), project_scope.md, the final report, and figures/
data/raw/       Original downloaded datasets, untouched
data/processed/ Every intermediate and final output the scripts produce
```

## Reproducing the pipeline

```
pip install -r requirements.txt
cd scripts
python3 01_preprocess.py                          # clean both raw datasets
python3 02_failure_probability_model.py            # discrete-time hazard model
python3 03_time_to_failure.py                      # TTF derived from the hazard curve
python3 04_workload_criticality_cost.py            # criticality tiers + migration cost model
python3 05_policy_design.py                        # the two policies + pre-simulation checks
python3 06_simulation_evaluation.py                # the replay simulator (naive + matched-budget comparison)
python3 07_correlated_assignment_experiment.py     # the resolving correlation-sweep experiment
python3 08_gqat_net_model.py                       # task 11: from-scratch NumPy attention model vs. HistGBM
```

`08_gqat_net_model.py` also runs `test_gqat_numpy_gradcheck.py`'s logic implicitly correct (that script itself
is a standalone verification step -- run `python3 test_gqat_numpy_gradcheck.py` on its own to re-verify the
hand-derived backward pass against numerical finite differences before trusting a training run). Both scripts
depend on `numpy_nn.py` and `gqat_net_numpy.py`, which have no other dependencies beyond `numpy`/`scipy`/
`scikit-learn` -- see `docs/task11_summary.md` for why (TensorFlow/PyTorch/Keras/JAX are all unavailable in the
sandbox this project was built in; this was confirmed, not assumed, before writing a from-scratch NumPy
neural network as the alternative).

Each script reads from `data/processed/` and/or `data/raw/`, and (over)writes its own outputs there — running them in order regenerates everything in this repo from the two raw datasets, including the large Azure VM tables (see below on why those are still committed directly rather than left to regeneration only).

To rebuild the Word report (`docs/VM_Mitigation_Policy_Report.docx`) from `docs/figures/` and the numbers in `scripts/build_report.js`:

```
cd scripts
npm install docx
node build_report.js
```

## Data sources and licensing

This project combines two real, independently-sourced datasets — no public dataset links real VM placement to real host failures (that internal linkage is what makes Microsoft's Narya possible inside Azure), so two real datasets stand in for the two sides of that picture:

- **`data/raw/azure/`** — the Azure Public Dataset V1 VM trace, Microsoft's own release, downloaded directly from its GitHub release (`github.com/Azure/AzurePublicDataset`, released under **CC BY 4.0** — attribution required, freely reusable). 2,013,767 real VMs over a 30-day trace.
- **`data/raw/backblaze/`** — a real per-drive survival summary (122,618 drives, 6,912 real failures, 2013–2017) derived directly from Backblaze's own published daily SMART/failure telemetry (`backblaze.com/cloud-storage/resources/hard-drive-test-data`, which Backblaze explicitly makes free to use). The specific summarized CSV bundled here was built by a third party, [vfonov/hdd_survival_backblaze](https://github.com/vfonov/hdd_survival_backblaze) — **that specific repository carries no explicit license file**, so if you plan to redistribute this repo further or make it public long-term, consider regenerating an equivalent summary directly from Backblaze's own raw quarterly files instead (the derivation method is documented in that repo's `import.sh`, and is straightforward: one row per drive with real failure/censored status and real age at that outcome). Included here with attribution for a research/coursework context.

### Getting the large Azure files

Three files exceed GitHub's 100MB per-file limit, so they are **not included** in this bundle as delivered: `data/raw/azure/vmtable.csv.gz` (~156MB, the original Azure release asset) and its two derivatives, `data/processed/azure_vms_clean.csv.gz` (~154MB, task 2's output) and `data/processed/azure_vms_with_costs.csv.gz` (~198MB, task 5's final per-VM output). Only the first is an actual external dependency — the other two are fully regenerated by this repo's own scripts:

```
mkdir -p data/raw/azure
curl -L -o data/raw/azure/vmtable.csv.gz \
  https://github.com/Azure/AzurePublicDataset/releases/download/dataset-v1/trace_data_vmtable_vmtable.csv.gz

cd scripts
python3 01_preprocess.py                  # regenerates data/processed/azure_vms_clean.csv.gz
python3 04_workload_criticality_cost.py   # regenerates data/processed/azure_vms_with_costs.csv.gz
```

That URL is Microsoft's own GitHub release asset for the Azure Public Dataset V1 (CC BY 4.0) — the same file this project used throughout, unmodified. The two `python3` commands take under a minute combined and reproduce the exact processed files this project used (they also regenerate `data/processed/backblaze_drives_clean.csv` and the Backblaze summary tables from the small raw file that *is* included, so running the full pipeline from `01` through `07` reproduces everything in `data/processed/` from just the two raw sources).

`setup_and_push.sh` runs both of the steps above automatically before pushing. `.gitattributes` already routes all 3 of these files through **Git LFS** once they exist locally, so once fetched/regenerated, a plain `git add .` / `git commit` / `git push` handles them correctly — no manual `git lfs track` step needed.

Everything else in this repo — every other real dataset, every intermediate table, every script, every report — is included directly; Git LFS is only needed for these 3 files.

## Pushing this to GitHub

This repo (`https://github.com/Rag2102/ccproject`) already exists and is ready to receive this content:

```
cd vm-mitigation-repo                 # this folder
bash setup_and_push.sh                # fetches/regenerates the 3 large files, sets up Git LFS,
                                       # then git init + add + commit + push to Rag2102/ccproject
```

Run this from a **real terminal on your Mac** (Terminal.app, iTerm, etc.) — not through an AI assistant's sandboxed workspace, which typically has no general internet access and doesn't hold your GitHub credentials. Your regular terminal is wherever you're already signed in to GitHub (SSH key, `gh auth login`, or the macOS credential manager), and it needs Homebrew (to auto-install `git-lfs` if it isn't already there) or `git-lfs` pre-installed.

If you'd rather skip the 3 large files entirely (smaller, faster push), just delete the `data/raw/azure/vmtable.csv.gz` line's `curl` step's effect by not running it, remove `.gitattributes`, and run `git init && git add . && git commit` manually — everything else in the repo (including the live demo) works fully without them.

## Key findings, at a glance

See `docs/task*_summary.md` for full detail on each stage. In order:

1. **Data** (`data_summary.md`) — real datasets combined; drive model, not age, dominates real failure risk (one Seagate batch fails at 36% vs 3–8% for others — the real, publicly-known bad batch).
2. **Failure probability** (`task3_summary.md`) — discrete-time hazard model, ROC-AUC 0.781, properly calibrated (a first attempt using class-balancing was caught and corrected because it would have silently broken the downstream cost math).
3. **Time-to-failure** (`task4_summary.md`) — derived from the same hazard curve; concordance index 0.71 against real outcomes.
4. **Criticality & cost** (`task5_summary.md`) — migration cost grounded in the classic live-migration pre-copy formula (Clark et al., NSDI 2005), using real VM memory/vCPU/CPU-utilization data.
5. **Policy design** (`task6_7_summary.md`) — the cost-sensitive decision rule and its threshold baseline, validated on hand-built scenarios and a full real-data decision surface.
6. **Simulation** (`task8_summary.md`) — the honest result: a naive comparison favored cost-sensitivity, but the fair (matched-budget) comparison didn't confirm it, and diagnosed why (random VM-to-host assignment removes any signal for cost-awareness to exploit).
7. **Resolving experiment** (`task9_summary.md`) — sweeping the correlation between workload criticality and host risk recovers the hypothesized advantage once ρ ≳ 0.3, with a clean monotonic curve.
8. **GQAT-Net comparison** (`task11_summary.md`) — a from-scratch NumPy re-implementation of a real published attention-based failure model (Tripathi et al. 2025), gradient-checked and trained on the same data/split as the HistGBM model; the calibrated tree model still wins on every metric, especially calibration (Brier 0.002 vs. 0.067) — reinforcing task 3's central lesson that calibration, not architecture sophistication, is what makes a probability usable inside a cost formula.
