# Deploying the AWS architecture

This is a second, more substantial deployment alongside the Render one (see
the root `README.md`'s "See it working" section) -- built specifically to
demonstrate real cloud-native architecture: a static CDN-served frontend,
a serverless JSON API, and a genuinely distributed simulation. See
`docs/cloud_architecture.md` for the full design rationale and diagram,
and `docs/openapi.yaml` for the API contract (generated from the live
model data by `scripts/generate_openapi.py`, not hand-typed).

Everything here runs in **your own AWS account** using **your own AWS
credentials** -- nothing in this repo has (or could have) your credentials.
Run every command below from a real terminal on your own machine.

## Prerequisites

- An AWS account, with the AWS CLI installed and configured (`aws configure`
  -- this is where you enter your own access key, not something to paste
  into a chat with an AI assistant).
- [Terraform](https://developer.hashicorp.com/terraform/install) (`brew
  install terraform` on a Mac).
- Docker Desktop, running.

## 1. Create the ECR repositories (phase 1 of 2)

The Lambda functions below reference a container image that has to already
exist in ECR before Terraform can create them -- so this is a two-phase
apply. First, just the repositories:

```bash
cd cloud/infra
terraform init
terraform apply \
  -target=aws_ecr_repository.api \
  -target=aws_ecr_repository.sim_worker \
  -target=aws_ecr_repository.sim_aggregator
```

Note the three repository URLs Terraform prints (or run `terraform output`
afterwards).

## 2. Build and push the 3 container images

From the **repo root** (not `cloud/infra`):

```bash
# Log Docker in to your ECR registry (replace <account-id>/<region> or copy
# the exact command from the AWS Console -> ECR -> your repo -> "View push
# commands")
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# IMPORTANT: --platform linux/amd64 on every build below. Lambda's default
# architecture is x86_64; if you're on an Apple Silicon Mac, Docker builds
# arm64 images by default, which will fail at invoke time with an
# "exec format error" if you skip this flag.

docker build --platform linux/amd64 -f cloud/api/Dockerfile -t vm-mitigation-api .
docker tag vm-mitigation-api:latest <ecr_api_repository_url>:latest
docker push <ecr_api_repository_url>:latest

docker build --platform linux/amd64 -f cloud/sim/Dockerfile.worker -t vm-mitigation-sim-worker .
docker tag vm-mitigation-sim-worker:latest <ecr_sim_worker_repository_url>:latest
docker push <ecr_sim_worker_repository_url>:latest

docker build --platform linux/amd64 -f cloud/sim/Dockerfile.aggregator -t vm-mitigation-sim-aggregator .
docker tag vm-mitigation-sim-aggregator:latest <ecr_sim_aggregator_repository_url>:latest
docker push <ecr_sim_aggregator_repository_url>:latest
```

The sim-worker image bundles the ~198MB `azure_vms_with_costs.csv.gz` (it
genuinely needs the full per-VM table -- see `docs/cloud_architecture.md`),
so that push will take a few minutes on a normal connection. The other two
are small.

## 3. Deploy everything else (phase 2 of 2)

If you already ran `terraform init` once before this project added AWS
WAF and the CloudFront-to-API-Gateway shared secret (`waf.tf`,
`s3_frontend.tf`), run `terraform init -upgrade` once first -- it added a
new provider (`hashicorp/random`) that a plain `terraform apply` won't
pick up on its own. A first-time `terraform init` already covers this.

```bash
cd cloud/infra
terraform apply
```

This creates the Lambda functions (now that their images exist), the API
Gateway, the S3 buckets + the frontend's static files (including a
generated `config.js` pointing at the API same-origin, via CloudFront --
see below), the CloudFront distribution (now fronting both the frontend
*and* the API, with AWS WAF attached), and the Step Functions state
machine.

```bash
terraform output
```

`frontend_url` is your shareable live-demo link, and also how you reach
the API now: `https://<frontend_url>/api/predict` etc, proxied through
the same CloudFront distribution. The `api_url` output (the raw API
Gateway invoke URL) is intentionally no longer callable directly -- it
403s anything that doesn't carry the shared secret header only CloudFront
knows, which is what lets WAF actually protect the API (HTTP APIs can't
take a usage plan, an API key, or WAF directly -- see `cloud/infra/
waf.tf`'s comment for the full reasoning). **CloudFront can take 5-15
minutes to fully propagate after first creation** -- if it doesn't load
immediately, that's why; give it a few minutes and retry.

## 4. Run the distributed simulation

The correlation-sweep experiment (originally a 4-point, single-seed local
loop in `scripts/07_correlated_assignment_experiment.py`) now runs as 55
independent Lambda invocations (11 rho values x 5 seeds each, fanned out by
a Step Functions Map state) and gets aggregated with a real mean/std across
seeds:

```bash
aws stepfunctions start-execution \
  --state-machine-arn "$(terraform output -raw sim_state_machine_arn)" \
  --input file://../sim/trials.json \
  --name manual-run-1
```

That returns immediately with an `executionArn`. Check on it:

```bash
aws stepfunctions describe-execution --execution-arn <executionArn from above>
```

Once `"status": "SUCCEEDED"` (usually 1-3 minutes for 55 trials at the
default concurrency of 10), download the results:

```bash
aws s3 cp "s3://$(terraform output -raw sim_results_bucket)/sim-results/correlated_assignment_sweep_aggregated.csv" .
aws s3 cp "s3://$(terraform output -raw sim_results_bucket)/sim-results/correlated_assignment_sweep_raw.csv" .
```

Want a finer or coarser sweep? Edit `cloud/sim/trials.json` (or regenerate
it with different `rho_values`/`seeds` -- see the generator snippet in
`docs/cloud_architecture.md`) and re-run `start-execution` with the new
file. No redeploy needed -- the trial list is just the execution's input,
not baked into any Lambda or the state machine.

## 5. (Optional) Get alerted when something breaks

`terraform apply` also creates an SNS topic and 5 CloudWatch alarms
(errors, throttling, near-timeout duration, API Gateway 5xx, failed
simulation executions -- see `docs/observability.md` for the full list
and reasoning). Terraform can't subscribe your email to it without
hardcoding your address into version-controlled infra, so do it yourself
once:

```bash
aws sns subscribe --topic-arn "$(terraform output -raw alerts_topic_arn)" \
  --protocol email --notification-endpoint you@example.com
```

Then confirm the email AWS sends you -- the subscription stays "pending
confirmation" and silent until you click that link.

## 6. (Optional) Load-test the live API

`scripts/load_test.py` (repo root, not `cloud/`) sends a batch of
concurrent `/api/predict` requests with realistic payloads (drawn live
from `/api/meta`, so they always match whatever categories the deployed
models actually support) and reports latency percentiles and the status
code breakdown. Needs `pip install -r requirements-dev.txt` for
`requests`, and a network that can actually reach your deployed URL (this
can't be run from inside an offline dev sandbox -- see the script's own
docstring):

```bash
python3 scripts/load_test.py --url "$(terraform output -raw frontend_url)"
```

The default concurrency (5) stays comfortably under both rate limits this
project ships (the API Gateway stage throttle and the WAF rate rule --
`cloud/infra/api_gateway.tf`, `cloud/infra/waf.tf`). Raising
`--concurrency` well past that is a legitimate way to confirm those
limits actually engage (`--help` for all options); you should start
seeing HTTP 429s, which the script calls out explicitly rather than
reporting as a plain failure.

## Cost

Designed to stay inside AWS's free tier for occasional/demo use: Lambda
(1M free requests/month), API Gateway HTTP API (1M free requests/month for
12 months), CloudFront (1TB free egress/month for 12 months), Step
Functions (4,000 free state transitions/month), S3 (5GB free for 12
months). The one thing that isn't free indefinitely is ECR storage past
500MB total (the sim-worker image alone, with the bundled 198MB dataset, is
likely to exceed that) -- a few cents/month at most for a repo this size.

**AWS WAF (`waf.tf`) is the one addition here that is never free**, tier or
no tier: roughly $5/month flat for the web ACL plus $1/month per rule (3
rules = $3/month here) plus ~$0.60 per million requests it evaluates --
call it ~$8-9/month minimum while the distribution exists, independent of
how much the demo actually gets used. `terraform destroy` when you're done
demoing (below) stops this the same as everything else; there's no way to
keep the rest of this free-tier-friendly and still have WAF protect the
API, since WAF is what makes that protection possible at all on an HTTP
API (see `waf.tf`'s comment).

When you're done demonstrating this and want zero ongoing cost:

```bash
cd cloud/infra
terraform destroy
```

## If something breaks

Paste the exact error back and it can be fixed the same way the Render
deploy issues were: this is real infrastructure with real failure modes
(IAM permission edges, image architecture mismatches, CORS), and there's a
good chance the very first `terraform apply` surfaces something to fix,
just like the first Render deploy did.
