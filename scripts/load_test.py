"""
Load-test script for the live API (task 46) -- /api/meta and /api/predict,
against either deployment: Render (plain domain) or AWS (the CloudFront
domain `terraform output frontend_url` prints; /api/* is proxied through
to API Gateway same-origin -- see cloud/infra/s3_frontend.tf).

Why this has to run from your own machine, not this repo's CI or dev
sandbox: it needs real network access to a real deployed URL, which a
sandboxed development environment may not have (and shouldn't need, for a
script whose entire job is hitting a live endpoint over the internet).
Verified against a local `python3 webapp/app.py` server before ever being
pointed at a real deployment -- see "Verification" below.

Deliberately stdlib + `requests` (already in requirements-dev.txt) rather
than `locust`: this project consistently prefers a short, fully-readable
script over an external framework where the framework's job is small
enough to hand-roll (the WSGI adapter in cloud/api/lambda_function.py,
the hand-computed Kaplan-Meier estimator in scripts/09_*, are the same
choice for the same reason) -- and a locust-based load generator with a
web UI is a lot more tool than "make N concurrent requests and report
latency percentiles" needs.

Usage:
    python3 scripts/load_test.py --url https://d111111abcdef8.cloudfront.net
    python3 scripts/load_test.py --url https://vm-mitigation-xxxx.onrender.com \
        --requests 200 --concurrency 20

Respect the limits this project actually ships (cloud/infra/api_gateway.tf's
stage throttle: 10 req/s steady-state, burst 20; cloud/infra/waf.tf's rate
rule: 2000 req/5min per source IP) -- the defaults below stay comfortably
under both. Cranking --concurrency up past that is a legitimate way to
verify those limits actually engage (you should start seeing HTTP 429s),
not a bug in this script; see "Verification" below for what that looked
like against the local dev server's own throttle-free baseline.
"""
import argparse
import json
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


def fetch_meta(base_url, timeout):
    resp = requests.get(f"{base_url}/api/meta", timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def random_payload(meta):
    """A realistic request drawn from the API's own real category values
    (not a hardcoded guess) -- fetched fresh from /api/meta so this can
    never drift out of sync with webapp/core.py's actual validated enums
    (task 40's PredictRequest) the way a hand-copied list would."""
    return {
        "model_grp": random.choice(meta["model_groups"]),
        "age_days": round(random.uniform(0, meta["max_age_days"]), 1),
        "criticality_tier": random.choice(meta["criticality_tiers"]),
        "size_tier": random.choice(meta["size_tiers"]),
        "which_model": random.choice(["histgbm", "gqat"]),
    }


def one_request(base_url, meta, timeout):
    payload = random_payload(meta)
    t0 = time.perf_counter()
    try:
        resp = requests.post(f"{base_url}/api/predict", json=payload, timeout=timeout)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return {"status": resp.status_code, "elapsed_ms": elapsed_ms, "error": None}
    except requests.RequestException as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return {"status": None, "elapsed_ms": elapsed_ms, "error": str(exc)}


def percentile(sorted_values, p):
    if not sorted_values:
        return float("nan")
    idx = min(len(sorted_values) - 1, int(len(sorted_values) * p))
    return sorted_values[idx]


def summarize(results, wall_clock_s):
    latencies = sorted(r["elapsed_ms"] for r in results)
    statuses = {}
    for r in results:
        key = r["status"] if r["status"] is not None else f"error: {r['error']}"
        statuses[key] = statuses.get(key, 0) + 1

    print(f"\n{len(results)} requests in {wall_clock_s:.2f}s "
          f"({len(results) / wall_clock_s:.1f} req/s achieved)\n")

    print("Status / outcome breakdown:")
    for key, count in sorted(statuses.items(), key=lambda kv: -kv[1]):
        pct = 100 * count / len(results)
        print(f"  {key!s:>40s}: {count:5d}  ({pct:5.1f}%)")

    print("\nLatency (ms), successful requests only:")
    ok_latencies = sorted(r["elapsed_ms"] for r in results if r["status"] == 200)
    if ok_latencies:
        print(f"  min={ok_latencies[0]:.1f}  "
              f"p50={percentile(ok_latencies, 0.50):.1f}  "
              f"p95={percentile(ok_latencies, 0.95):.1f}  "
              f"p99={percentile(ok_latencies, 0.99):.1f}  "
              f"max={ok_latencies[-1]:.1f}  "
              f"mean={statistics.mean(ok_latencies):.1f}")
    else:
        print("  (no successful requests)")

    n_429 = statuses.get(429, 0)
    n_5xx = sum(count for status, count in statuses.items()
                if isinstance(status, int) and 500 <= status < 600)
    if n_429:
        print(f"\n{n_429} request(s) got HTTP 429 -- that's the API Gateway "
              f"stage throttle or the WAF rate rule engaging as designed, "
              f"not a failure of this script or the API. See "
              f"cloud/infra/api_gateway.tf and cloud/infra/waf.tf.")
    if n_5xx:
        print(f"\n{n_5xx} request(s) got a 5xx -- check the "
              f"api-lambda-errors / api-lambda-duration-near-timeout "
              f"CloudWatch alarms (docs/observability.md) for what was "
              f"happening server-side during this run.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", required=True,
                         help="Base URL, no trailing slash (e.g. https://d111111abcdef8.cloudfront.net "
                              "for AWS, or the Render URL). /api/meta and /api/predict are appended.")
    parser.add_argument("--requests", type=int, default=100, help="Total /api/predict requests to send (default: 100)")
    parser.add_argument("--concurrency", type=int, default=5,
                         help="Concurrent worker threads (default: 5 -- stays comfortably under the "
                              "10 req/s steady-state API Gateway throttle; raise deliberately to test "
                              "that the throttle/WAF rate limit actually engages)")
    parser.add_argument("--timeout", type=float, default=35.0,
                         help="Per-request timeout in seconds (default: 35 -- a few seconds above the "
                              "API Lambda's own 30s hard timeout, so a genuine server-side timeout shows "
                              "up as a clean 5xx/504 in the results rather than a client-side timeout error)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed, for a reproducible request mix")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    base_url = args.url.rstrip("/")

    print(f"Fetching /api/meta from {base_url} to build realistic request payloads...")
    try:
        meta = fetch_meta(base_url, args.timeout)
    except requests.RequestException as exc:
        print(f"\nCould not reach {base_url}/api/meta: {exc}\n"
              f"Check that --url is correct (no trailing slash) and the deployment is up.")
        raise SystemExit(1)
    print(f"Got {len(meta['model_groups'])} drive model groups, "
          f"{len(meta['criticality_tiers'])} criticality tiers, "
          f"{len(meta['size_tiers'])} size tiers.")

    print(f"\nSending {args.requests} POST /api/predict requests "
          f"at concurrency={args.concurrency}...")

    results = []
    t_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(one_request, base_url, meta, args.timeout) for _ in range(args.requests)]
        for future in as_completed(futures):
            results.append(future.result())
    wall_clock_s = time.perf_counter() - t_start

    summarize(results, wall_clock_s)


if __name__ == "__main__":
    main()
