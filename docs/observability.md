# Observability: structured logging + CloudWatch alarms

## Why this exists

Up to this point the project could tell you *whether* the live demo was
up (open the URL, click Run) but had no way to answer "how many people
used it today," "which drive model do people actually test with," or
"did it start erroring an hour ago and nobody noticed" -- for either
deployment. This closes both gaps: one structured log line per prediction
request (both deployments already capture stdout for free), and five
CloudWatch alarms on the AWS deployment's actual failure modes.

## Structured logging (`webapp/core.py`)

`run_predict()` emits exactly one JSON object per call, via `print()` (see
that function's own comment for why plain `print()` rather than the
`logging` module -- mainly testability: a `logging.StreamHandler` created
once at import time keeps writing to whatever object `sys.stdout` was
bound to back then, which breaks under pytest's `capsys`, while `print()`
always resolves the *current* `sys.stdout`). Two event types:

- `predict_served` -- a successful prediction: `model_grp`, `which_model`,
  `age_days`, `criticality_tier`, `size_tier`, `p_fail_within_window`,
  `cost_sensitive_migrate`, `threshold_migrate`, and `duration_ms` (pure
  inference time -- model call + policy math -- not end-to-end request
  latency, since that would also include cold start and whatever
  Flask/API Gateway/CloudFront add around it).
- `predict_rejected` -- task 40's input validation rejected the request:
  `errors`, the same field-level messages the HTTP 400 response body
  carries.

None of these fields are personal data -- drive model, age-in-days,
workload criticality/size tier are fleet/VM metadata, not anything
user-identifying, so there's nothing here that needs redacting or a
retention policy stricter than the CloudWatch log groups' existing 14-day
retention (`cloud/infra/lambda.tf`).

Both deployments capture this for free, with zero extra wiring:

- **Render**: stdout goes straight to Render's own log viewer.
- **AWS**: Lambda automatically ships a function's stdout to its
  CloudWatch log group (`/aws/lambda/vm-mitigation-api`). Query it with
  CloudWatch Logs Insights, e.g. to see the last hour's predicted failure
  probabilities by drive model:
  ```
  fields model_grp, p_fail_within_window, duration_ms
  | filter event = "predict_served"
  | sort @timestamp desc
  | limit 50
  ```
  or to count rejected requests by reason over the last day:
  ```
  fields errors
  | filter event = "predict_rejected"
  | stats count() by errors
  ```

## CloudWatch alarms (`cloud/infra/observability.tf`, AWS deployment only)

Five alarms, all publishing to one SNS topic (`aws_sns_topic.alerts`):

| Alarm | Fires when | Why it matters |
|---|---|---|
| `api-lambda-errors` | API Lambda `Errors` > 0 in 5 min | An unhandled exception reached the Lambda runtime -- something task 40's validation and normal error handling didn't catch. |
| `api-lambda-throttles` | API Lambda `Throttles` > 0 in 5 min | Concurrent executions hit the limit; requests are failing outright, not queuing. |
| `api-lambda-duration-near-timeout` | p99 `Duration` > 25s in 5 min | Within 5s of the Lambda's 30s timeout (also API Gateway HTTP API's own hard integration ceiling) -- the exact failure mode that caused intermittent 503s before memory was bumped to 3008MB (see `lambda.tf`'s comment). |
| `api-gateway-5xx` | API Gateway `5xx` count > 0 in 5 min | A real server-side failure reached a client. Check the Lambda alarms above first -- they're the most likely cause. |
| `sim-execution-failures` | Step Functions `ExecutionsFailed` > 0 in 5 min | A full correlation-sweep simulation run failed (not the same as a single trial retrying inside the Map state -- Retry/Catch already absorbs those). |

Deliberately **not** alarming on API Gateway 4xx: task 40 made a 400 an
expected, routine response to a malformed request (a fat-fingered demo
form submission, a scanner probing the endpoint), not an incident --
alarming on it would just be noise.

Terraform creates the SNS topic but does not subscribe an email to it
(that would mean hardcoding a personal address into version-controlled
infra). After `terraform apply`, subscribe yourself:

```bash
aws sns subscribe --topic-arn "$(terraform output -raw alerts_topic_arn)" \
  --protocol email --notification-endpoint you@example.com
```

then confirm the email AWS sends -- SNS email subscriptions stay
"pending confirmation" and silent until that link is clicked.

## What's deliberately not here

- **No log aggregation service beyond CloudWatch itself** (no
  ELK/Datadog/etc.) -- CloudWatch Logs Insights is enough to query
  structured JSON lines for a project this size, and adding a third-party
  log pipeline would be infrastructure this demo doesn't need.
- **No dashboard** -- the alarms plus Logs Insights queries above cover
  "is something wrong" and "what was happening when it went wrong";
  a CloudWatch dashboard would be a nice-to-have visualization on top,
  not something this project's actual traffic volume needs.
- **No tracing (X-Ray)** -- the request path is short enough (CloudFront
  -> API Gateway -> one Lambda) that step-by-step tracing wouldn't add
  much over what the structured `duration_ms` field and the alarms above
  already show.
