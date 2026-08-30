"""
AWS Lambda handler (deployed as a container image) that serves the exact
same Flask app as webapp/app.py -- the one already running on Render --
via a small hand-rolled WSGI <-> API Gateway HTTP API (payload format 2.0)
adapter. No third-party adapter package (aws-wsgi/mangum/serverless-wsgi):
one less external dependency between "what we tested locally" and "what's
actually deployed," and API Gateway's v2.0 event shape is simple enough
that a ~50-line adapter is easy to read and verify in full.

Deployed behind an API Gateway HTTP API with a Lambda proxy integration
(see cloud/infra/*.tf). Only /api/meta and /api/predict are actually called
by the static frontend (cloud/frontend/) -- `/` and `/figures/<f>` still
work (inherited unchanged from webapp/app.py) but the frontend doesn't hit
them; S3 + CloudFront serve the HTML and PNG figures directly instead,
which is faster and doesn't spend a Lambda invocation on a static file.
"""
import base64
import io
import sys
from pathlib import Path

# webapp/app.py does a bare `import core` (it runs standalone as
# `python3 app.py` from inside webapp/, which is what makes that work --
# Python puts a script's own directory on sys.path). Adding webapp/ to
# sys.path here reproduces that exact condition instead of restructuring
# app.py's imports, so app.py is byte-for-byte identical across both
# deployments.
WEBAPP_DIR = Path(__file__).resolve().parent / "webapp"
sys.path.insert(0, str(WEBAPP_DIR))
from app import app as flask_app  # noqa: E402

_TEXTUAL_CONTENT_TYPE_PREFIXES = ("text/", "application/json", "application/javascript")


def _wsgi_environ_from_event(event):
    """API Gateway HTTP API payload format 2.0 -> a WSGI environ dict."""
    request_context = event.get("requestContext", {})
    http = request_context.get("http", {})
    method = http.get("method", "GET")
    raw_path = event.get("rawPath", "/")
    query_string = event.get("rawQueryString", "") or ""

    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    cookies = event.get("cookies")
    if cookies:
        headers["cookie"] = "; ".join(cookies)

    raw_body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body_bytes = base64.b64decode(raw_body)
    else:
        body_bytes = raw_body.encode("utf-8")

    environ = {
        "REQUEST_METHOD": method,
        "SCRIPT_NAME": "",
        "PATH_INFO": raw_path,
        "QUERY_STRING": query_string,
        "SERVER_NAME": headers.get("host", "lambda"),
        "SERVER_PORT": "443",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": headers.get("x-forwarded-proto", "https"),
        "wsgi.input": io.BytesIO(body_bytes),
        "wsgi.errors": sys.stderr,
        "wsgi.multithread": False,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
        "CONTENT_LENGTH": str(len(body_bytes)),
    }
    for key, value in headers.items():
        wsgi_key = key.upper().replace("-", "_")
        if wsgi_key in ("CONTENT_TYPE", "CONTENT_LENGTH"):
            environ[wsgi_key] = value
        else:
            environ[f"HTTP_{wsgi_key}"] = value
    return environ


def handler(event, context):
    environ = _wsgi_environ_from_event(event)
    response_meta = {}

    def start_response(status, response_headers, exc_info=None):
        response_meta["status"] = int(status.split(" ", 1)[0])
        response_meta["headers"] = response_headers

    body_iter = flask_app.wsgi_app(environ, start_response)
    body_bytes = b"".join(body_iter)

    headers_dict = dict(response_meta["headers"])
    content_type = headers_dict.get("Content-Type", "")
    is_text = any(content_type.startswith(p) for p in _TEXTUAL_CONTENT_TYPE_PREFIXES)

    if is_text:
        return {
            "statusCode": response_meta["status"],
            "headers": headers_dict,
            "body": body_bytes.decode("utf-8", errors="replace"),
            "isBase64Encoded": False,
        }
    return {
        "statusCode": response_meta["status"],
        "headers": headers_dict,
        "body": base64.b64encode(body_bytes).decode("ascii"),
        "isBase64Encoded": True,
    }
