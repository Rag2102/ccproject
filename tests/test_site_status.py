"""
Tests for webapp/status.json, the one place the site's progress is set, and
webapp/site_status.py, which derives the phase states and bar widths from it.
A bad edit to the file (a typo'd week, phases with a gap, a date that is not
a date) fails here instead of showing up wrong on the live site.
"""
import json
from datetime import date

import pytest

import site_status


@pytest.fixture
def st():
    return site_status.load_status()


def test_required_fields(st):
    for k in ("updated", "weeks_total", "weeks_done", "code_ready_to", "paper_week", "headline", "summary", "benchmark", "next", "phases"):
        assert k in st, k
    date.fromisoformat(st["updated"])


def test_weeks_are_consistent(st):
    assert 0 <= st["weeks_done"] <= st["code_ready_to"] <= st["weeks_total"]
    assert 1 <= st["paper_week"] <= st["weeks_total"]


def test_phases_cover_every_week_once(st):
    weeks = [w for ph in st["phases"] for w in range(ph["from"], ph["to"] + 1)]
    assert weeks == list(range(1, st["weeks_total"] + 1))


def test_phase_states_follow_the_weeks(st):
    for ph in st["phases"]:
        if ph["to"] <= st["weeks_done"]:
            assert ph["state"] == "done", ph["name"]
        elif ph["from"] <= st["code_ready_to"]:
            assert ph["state"] == "now", ph["name"]
        else:
            assert ph["state"] == "todo", ph["name"]
    # states only move forward through the plan: done, then under way, then to do
    order = {"done": 0, "now": 1, "todo": 2}
    states = [order[ph["state"]] for ph in st["phases"]]
    assert states == sorted(states)


def test_bar_shares(st):
    assert st["done_pct"] == round(100 * st["weeks_done"] / st["weeks_total"], 1)
    assert 0 <= st["done_pct"] + st["ready_pct"] <= 100


def test_a_later_week_moves_the_states(tmp_path):
    raw = json.loads(site_status.STATUS_FILE.read_text())
    raw.update(weeks_done=26, code_ready_to=40, updated="2027-04-04")
    f = tmp_path / "status.json"
    f.write_text(json.dumps(raw))
    st = site_status.load_status(f)
    by_name = {ph["name"]: ph["state"] for ph in st["phases"]}
    assert by_name["Paper, artifact, console"] == "done"
    assert by_name["Polish and submit paper A"] == "now"
    assert by_name["Ground the cost model"] == "todo"
    assert st["updated_text"] == "4 Apr 2027"
