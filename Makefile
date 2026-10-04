# v2 targets (v5 plan, Part I section 6). Targets not built yet print "not yet".
# v1 is run as documented in README.md; nothing here changes it.
PY ?= .venv/bin/python

.PHONY: test diag data train sim worlds bench stats numbers figures paper console reproduce-small reproduce release

test:
	$(PY) -m pytest tests -q

# Week 3: v1 anomaly diagnosis (about 10 s); writes results/summary/v1_anomaly.json and results/figures/v1_anomaly_*.pdf
diag:
	$(PY) scripts/v2/diag_v1_anomaly.py

data train worlds bench stats numbers figures paper console reproduce-small reproduce release:
	@echo "make $@: not yet (see docs/plan, Part I section 6 for the week it first works)"

sim: worlds bench
