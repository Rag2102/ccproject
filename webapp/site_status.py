"""The site's progress (status.json), with what follows from its numbers.

status.json is the one place the progress shown on the site is set; app.py reads it on every request, so an
edit shows without a restart. tests/test_site_status.py checks the file.
"""
import json
from datetime import date
from pathlib import Path

STATUS_FILE = Path(__file__).with_name("status.json")


def load_status(path=STATUS_FILE):
    """status.json plus each phase's state, the progress bar's shares and a readable date.
    A phase is done when it ends by weeks_done, under way when it starts by code_ready_to, otherwise to do."""
    st = json.loads(Path(path).read_text())
    total, done, ready = st["weeks_total"], st["weeks_done"], st["code_ready_to"]
    for ph in st["phases"]:
        ph["state"] = "done" if ph["to"] <= done else "now" if ph["from"] <= ready else "todo"
    st["done_pct"] = round(100 * done / total, 1)
    st["ready_pct"] = round(100 * (ready - done) / total, 1)
    st["paper_pct"] = round(100 * st["paper_week"] / total, 1)
    d = date.fromisoformat(st["updated"])
    st["updated_text"] = f"{d.day} {d:%b %Y}"
    return st
