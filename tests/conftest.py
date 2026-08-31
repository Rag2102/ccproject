import sys
from pathlib import Path

# webapp/ isn't a package (no __init__.py) -- it's imported this way by both
# app.py and cloud/api/lambda_function.py too, so tests follow the same
# convention rather than turning it into a package just for pytest's sake.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webapp"))
