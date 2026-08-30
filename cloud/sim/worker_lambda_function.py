"""
Lambda handler for one (rho, seed) trial of the correlation-sweep
simulation. Invoked by the Step Functions Map state in cloud/infra (one
invocation per trial, run concurrently) -- see docs/cloud_architecture.md
for the full picture.

Event shape: {"rho": <float>, "seed": <int>}
Returns: the dict sim_core.simulate_one() produces (JSON-serializable).

DATA is loaded once per warm Lambda container (module-level global), not
once per invocation -- the 198MB VM table is the expensive part (~20s to
parse); Step Functions Map will reuse a warm container across several of
its concurrent lanes' subsequent invocations where the runtime allows it,
so this amortizes that cost across trials, exactly like core.py's
load-once-at-import pattern in the API Lambda.
"""
from pathlib import Path

import sim_core

DATA_DIR = Path(__file__).resolve().parent / "data"
_DATA = None


def _get_data():
    global _DATA
    if _DATA is None:
        _DATA = sim_core.load_data(data_dir=DATA_DIR)
    return _DATA


def handler(event, context):
    rho = float(event["rho"])
    seed = int(event["seed"])
    data = _get_data()
    return sim_core.simulate_one(data, rho, seed)
