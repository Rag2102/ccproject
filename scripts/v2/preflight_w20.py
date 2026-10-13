"""Pre-flight for run_rest.sh: every Week 20 phase at small scale, against the small matrix's
tuning files, writing into this checkout's results/raw/W20 (run it only in a scratch copy;
scripts/v2/preflight.sh does). The real 26_run_w20.py code runs unchanged; only its inputs (matrix,
Week 20 config, output folder, main-matrix tuning root) are pointed at small versions."""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("w20", ROOT / "scripts/v2/26_run_w20.py")
w20 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w20)

small = yaml.safe_load((ROOT / "configs/v2/matrix_small.yaml").read_text())
cfg = copy.deepcopy(yaml.safe_load((ROOT / "configs/v2/w20.yaml").read_text()))
cfg["seeds"] = [1, 1]
cfg["morris"].update({"seeds": [1, 1], "r": 2})
cfg["morris"]["p2_tuning"].update({"dev_seeds": [101, 101], "steps": 3})
cfg["failure_analysis"].update({"seeds": [1, 1], "budgets_pct": [2]})
cfg["robustness"]["settings"] = dict(list(cfg["robustness"]["settings"].items())[:3])

w20.load = lambda: (small, cfg)
real_tune_path = w20.rm.tune_path
small_root = ROOT / "results" / "small" / "raw"
w20.rm.tune_path = lambda root, regime, pct: real_tune_path(small_root, regime, pct)

for phase in ("ablate", "rtune", "robust", "morris", "failure"):
    getattr(w20, f"phase_{phase}")(small, cfg, None)
    print(f"preflight w20 {phase}: ok", flush=True)
w20.phase_collect()
print("preflight w20 collect: ok")
sys.exit(0)
