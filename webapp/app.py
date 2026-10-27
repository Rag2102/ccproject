"""
Task 12 -- a small Flask app that shows the project as a working model:
a "real findings" panel (the project's actual, already-validated headline
results) plus a live policy calculator that runs one of the two trained
failure-probability models (the calibrated HistGBM from task 3, or the
NumPy GQAT-Net-inspired model from task 11) on user-chosen inputs, builds
a hazard/survival curve on the fly, and shows both the cost-sensitive
policy and the threshold baseline's live decisions side by side.

This is NOT re-running the offline simulation (task 8/9) -- it's live,
single-VM inference through the actual trained models and the actual
policy.py decision functions, so what you see here is the real model
making a real decision on whatever inputs you give it, not a lookup into
a precomputed table.

All the actual logic lives in core.py, which this file just wraps in Flask
routes -- the exact same core.py also backs the AWS Lambda deployment (see
cloud/api/lambda_function.py), so both deployments are guaranteed to behave
identically.

Run from the project root:
    cd webapp && pip install flask && python3 app.py
Then open http://127.0.0.1:5000 in a browser.
"""
import os

from flask import Flask, render_template, request, jsonify, send_from_directory

import core
from site_status import load_status

app = Flask(__name__)


# One template, one page per section: every path renders the same document with that page shown, and
# the page script switches between them in place (with a transition) after the first load.
PAGES = {"how": "How it works", "model": "Live model", "v1": "v1 results", "models": "Models", "research": "Research v2",
         "brain": "Brain", "explore": "Explore"}


def render(page, title=None):
    return render_template("index.html", page=page, page_title=title, status=load_status(), **core.get_meta())


@app.route("/")
def index():
    return render("home")


@app.route("/<any(how, model, v1, models, research, brain, explore):name>")
def section(name):
    return render(name, PAGES[name])


@app.route("/api/brain")
def api_brain():
    """The records the Brain page answers from (built by scripts/build_brain.py from the claims ledger and the
    decision records); fetched only when that page is opened."""
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "brain.json", mimetype="application/json", max_age=300)


@app.route("/api/status")
def api_status():
    """The same progress as JSON (for the static frontend and anything else that wants it)."""
    return jsonify(load_status())


@app.route("/figures/<path:fname>")
def figures(fname):
    return send_from_directory(core.FIGURES, fname)


@app.route("/api/meta")
def api_meta():
    """Same data the `/` route renders server-side, as plain JSON -- used by
    the static S3/CloudFront frontend (cloud/frontend/) which has no server
    to render Jinja templates itself."""
    return jsonify(core.get_meta())


@app.route("/api/predict", methods=["POST"])
def predict():
    # silent=True: a malformed/non-JSON body returns None instead of Flask
    # raising its own 400 with an HTML error page -- we want a JSON error
    # body on every failure path, matching what both frontends' fetch()
    # calls expect to parse.
    body = request.get_json(silent=True)
    if body is None:
        return jsonify({"error": "request body must be valid JSON"}), 400
    try:
        return jsonify(core.run_predict(body))
    except core.InputValidationError as e:
        return jsonify({"error": "invalid input", "details": e.errors}), 400


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
