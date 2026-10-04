# v2 targets (v5 plan, Part I section 6). Targets not built yet print "not yet".
# v1 is run as documented in README.md; nothing here changes it.
PY ?= .venv/bin/python

.PHONY: test data train sim worlds bench stats numbers figures paper console reproduce-small reproduce release

test:
	$(PY) -m pytest tests -q

data train worlds bench stats numbers figures paper console reproduce-small reproduce release:
	@echo "make $@: not yet (see docs/plan, Part I section 6 for the week it first works)"

sim: worlds bench
