"""
Lambda handler that combines every (rho, seed) trial the Step Functions Map
state produced into the final correlation-sweep result: mean +/- std across
seeds at each rho, uploaded to S3 as two CSVs (raw per-trial, and the
per-rho aggregate that plays the same role as
data/processed/correlated_assignment_sweep.csv did for the original,
single-seed script 07).

Deliberately stdlib-only (csv/statistics/json) + boto3 (bundled in every
Lambda Python runtime) -- no pandas/numpy needed just to group-and-average
a few dozen small dicts, which keeps this image small and fast to build/push
independently of the worker image.

Event shape: the Map state's collected output, an array of the worker
Lambda's return dicts. See cloud/infra for how Step Functions wires the Map
state's result directly into this function's input.
"""
import csv
import io
import json
import os
import statistics
from collections import defaultdict

RESULT_BUCKET = os.environ.get("RESULT_BUCKET")
RESULT_PREFIX = os.environ.get("RESULT_PREFIX", "sim-results")

_NUMERIC_FIELDS = [
    "rho_achieved", "n_cs_migrations", "n_th_migrations", "tau_matched",
    "customer_impacting_failures_cs", "customer_impacting_failures_th",
    "total_cost_cs", "total_cost_th", "cost_sensitive_advantage_pct",
]


def _mean_std(values):
    mean = statistics.fmean(values)
    std = statistics.pstdev(values) if len(values) > 1 else 0.0
    return mean, std


def _to_csv_bytes(rows, fieldnames):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def handler(event, context):
    trials = event if isinstance(event, list) else event.get("trials", event)

    by_rho = defaultdict(list)
    for t in trials:
        by_rho[t["rho_target"]].append(t)

    aggregated = []
    for rho_target in sorted(by_rho):
        group = by_rho[rho_target]
        row = {"rho_target": rho_target, "n_seeds": len(group)}
        for field in _NUMERIC_FIELDS:
            mean, std = _mean_std([g[field] for g in group])
            row[f"{field}_mean"] = mean
            row[f"{field}_std"] = std
        aggregated.append(row)

    raw_fieldnames = ["rho_target", "seed"] + _NUMERIC_FIELDS
    agg_fieldnames = ["rho_target", "n_seeds"] + [
        f"{field}_{stat}" for field in _NUMERIC_FIELDS for stat in ("mean", "std")
    ]

    raw_csv = _to_csv_bytes(trials, raw_fieldnames)
    agg_csv = _to_csv_bytes(aggregated, agg_fieldnames)

    result = {
        "n_trials": len(trials),
        "n_rho_values": len(aggregated),
        "aggregated": aggregated,
    }

    if RESULT_BUCKET:
        import boto3  # imported lazily: not needed (or available) outside a real Lambda/AWS environment
        s3 = boto3.client("s3")
        s3.put_object(Bucket=RESULT_BUCKET, Key=f"{RESULT_PREFIX}/correlated_assignment_sweep_raw.csv", Body=raw_csv)
        s3.put_object(Bucket=RESULT_BUCKET, Key=f"{RESULT_PREFIX}/correlated_assignment_sweep_aggregated.csv", Body=agg_csv)
        s3.put_object(
            Bucket=RESULT_BUCKET,
            Key=f"{RESULT_PREFIX}/correlated_assignment_sweep_aggregated.json",
            Body=json.dumps(result, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        result["s3_bucket"] = RESULT_BUCKET
        result["s3_prefix"] = RESULT_PREFIX

    return result
