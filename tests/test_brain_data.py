"""
Tests for webapp/brain.json, the records the Brain page answers from (built by
scripts/build_brain.py from the claims ledger and the decision records). The
Brain only repeats these records, so each must carry an id, a title and the
text an answer shows, and no LaTeX macro name or markdown may leak through.
"""
import json
import re
from pathlib import Path

import pytest

BRAIN = Path(__file__).resolve().parents[1] / "webapp" / "brain.json"


@pytest.fixture(scope="module")
def data():
    return json.loads(BRAIN.read_text())


def test_source_is_recorded(data):
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["built"])
    assert "@" in data["source"]


def test_claims(data):
    ids = [c["id"] for c in data["claims"]]
    assert ids and len(ids) == len(set(ids))
    for c in data["claims"]:
        assert re.fullmatch(r"C\d+[a-z]?", c["id"])
        assert c["title"] and c["evidence"] and c["status"], c["id"]


def test_decisions(data):
    ids = [d["id"] for d in data["decisions"]]
    assert ids == sorted(ids) and len(ids) == len(set(ids))
    for d in data["decisions"]:
        assert re.fullmatch(r"ADR-\d{3}", d["id"])
        assert d["title"] and d["status"] and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d["date"]), d["id"]
        # every record has something an answer can say: a decision, or a status that carries it
        assert "decision" in d or len(d["status"]) > 20, d["id"]


def test_no_markup_leaks(data):
    text = json.dumps(data, ensure_ascii=False)
    assert "\\V" not in text and "`" not in text and "**" not in text
