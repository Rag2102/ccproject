# v2 targets (v5 plan, Part I section 6). Targets not built yet print "not yet".
# v1 is run as documented in README.md; nothing here changes it.
PY ?= .venv/bin/python

.PHONY: test diag data train sim worlds bench stats numbers figures paper console reproduce-small reproduce release

test:
	$(PY) -m pytest tests -q

# Week 3: v1 anomaly diagnosis (about 10 s); writes results/summary/v1_anomaly.json and results/figures/v1_anomaly_*.pdf
diag:
	$(PY) scripts/v2/diag_v1_anomaly.py

# Weeks 4-5: Backblaze archives -> Parquet (resumable; hours on first run, 35 GB download),
# then quality report, AFR, life table, Kaplan-Meier and the v1 check (about 5 min)
data:
	$(PY) scripts/v2/10_backblaze_ingest.py --all
	$(PY) scripts/v2/10a_backblaze_summaries.py

# Week 7: failure model v2 (hours; needs data/v2/features)
train:
	$(PY) scripts/v2/12_train.py

# Weeks 17-21: the frozen matrix (about 8 h on 8 cores for Weeks 18-19, 4 h more for Week 20)
bench:
	scripts/v2/run_w18.sh
	scripts/v2/run_w19.sh
	scripts/v2/run_w20.sh

# Statistics from results/raw (PROTOCOL v1.0 section 5): summaries, Holm, protocol check
stats:
	$(PY) scripts/v2/30_stats.py --groups A E B C D
	$(PY) scripts/v2/33_adaptive.py
	$(PY) scripts/v2/32_protocol_check.py --no-rerun

# Every figure and table from results/ files, never by re-running the simulator
figures: stats
	$(PY) scripts/v2/31_fig_f4.py
	$(PY) scripts/v2/27_pareto.py
	$(PY) scripts/v2/28_table3.py
	$(PY) scripts/v2/29_w20_analysis.py
	$(PY) scripts/v2/theory_check.py --quick

# Week 22: number macros for the paper (paper/numbers.tex); a test fails if a macro is missing
numbers:
	$(PY) scripts/v2/40_numbers.py

paper: numbers
	cd paper && latexmk -pdf -interaction=nonstopmode main.tex

# Week 22: static results Console (console/), data from results/summary at this commit
console:
	$(PY) scripts/v2/41_console_data.py
	@echo "open console/index.html (or: python3 -m http.server -d console 8040)"

# Week 21: reduced versions of every main figure in well under an hour on a laptop
reproduce-small:
	$(PY) scripts/v2/24_run_matrix.py --small --phase tune --groups A E B C D
	$(PY) scripts/v2/24_run_matrix.py --small --phase run --groups A E B C D --seeds 1-3
	$(PY) scripts/v2/24_run_matrix.py --small --phase collect --groups A E B C D --seeds 1-3
	$(PY) scripts/v2/30_stats.py --small --groups A E B C D
	$(PY) scripts/v2/31_fig_f4.py --small
	$(PY) scripts/v2/27_pareto.py --small
	$(PY) scripts/v2/28_table3.py --small
	$(PY) scripts/v2/33_adaptive.py --small
	@echo "figures in results/small/figures, summaries in results/small/summary"

worlds reproduce release:
	@echo "make $@: not yet (see docs/plan, Part I section 6 for the week it first works)"

sim: worlds bench
