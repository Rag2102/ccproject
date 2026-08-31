# Explicit log groups for all three Lambdas, with a real retention period.
# Without these, CloudWatch auto-creates a log group on first invocation
# with retention set to "Never expire" -- every request this project has
# already made (the curl tests, the 55-trial Step Functions run) has been
# quietly accumulating logs that were never going to age out on their own.
#
# NOTE -- these functions have already been invoked, so AWS already
# auto-created their log groups. Terraform will refuse to *create* a log
# group that already exists, so import each one once before the next
# apply:
#   terraform import aws_cloudwatch_log_group.api /aws/lambda/${var.project_name}-api
#   terraform import aws_cloudwatch_log_group.sim_worker /aws/lambda/${var.project_name}-sim-worker
#   terraform import aws_cloudwatch_log_group.sim_aggregator /aws/lambda/${var.project_name}-sim-aggregator
resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${var.project_name}-api"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "sim_worker" {
  name              = "/aws/lambda/${var.project_name}-sim-worker"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "sim_aggregator" {
  name              = "/aws/lambda/${var.project_name}-sim-aggregator"
  retention_in_days = 14
}

# All three Lambdas are container images (package_type = "Image") rather
# than zip uploads -- see cloud/README.md for why: pandas/scikit-learn/scipy
# are notoriously painful to package as Lambda zips (manylinux wheel
# builds, the 250MB unzipped/50MB direct-upload size limits), and a
# container image sidesteps all of that while also being the more
# "current practice" pattern for data-science-heavy Lambda functions.
#
# NOTE -- two-phase apply: these resources reference an image tag in ECR
# (ecr.tf) that must already have been pushed. Run `terraform apply
# -target=aws_ecr_repository.api -target=aws_ecr_repository.sim_worker
# -target=aws_ecr_repository.sim_aggregator` first, build+push the 3
# images (cloud/README.md has the exact docker commands), THEN run a plain
# `terraform apply` to create everything else including these functions.

resource "aws_lambda_function" "api" {
  function_name = "${var.project_name}-api"
  role          = aws_iam_role.api_lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.api.repository_url}:${var.api_image_tag}"
  # 3008MB (not 1024MB) -- Lambda allocates CPU proportional to configured
  # memory, and this function's cold start (importing pandas/scikit-learn/
  # scipy and loading two joblib models) measured ~24s at 1024MB in
  # CloudWatch, which is dangerously close to API Gateway HTTP API's
  # hard-capped 30s integration timeout (not configurable higher -- an AWS
  # platform ceiling) and is why requests were intermittently coming back
  # as 503. More memory buys more CPU to make that cold-start import/load
  # actually faster, rather than just hoping it finishes in time.
  memory_size = 3008
  timeout     = 30 # already at API Gateway HTTP API's own integration ceiling; raising this further wouldn't help

  environment {
    variables = {
      # Checked by cloud/api/lambda_function.py's handler() before it does
      # anything else -- a request without this exact value gets a 403.
      # Only CloudFront (s3_frontend.tf's api-gateway origin custom_header)
      # knows this value, so this is what actually stops the raw API
      # Gateway invoke_url from being called directly and bypassing WAF.
      # See waf.tf for why this exists instead of a REST API usage plan.
      ORIGIN_VERIFY_SECRET = random_password.origin_verify_secret.result
    }
  }
}

resource "aws_lambda_function" "sim_worker" {
  function_name = "${var.project_name}-sim-worker"
  role          = aws_iam_role.sim_worker_lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.sim_worker.repository_url}:${var.sim_worker_image_tag}"
  # Bumped alongside the api Lambda (see its comment) for the same cold-start
  # reason -- this one decompresses/parses a 198MB gzipped CSV at import
  # time, which is even more CPU-bound work. Unlike the api Lambda, this one
  # is invoked by Step Functions rather than sitting behind API Gateway's
  # 30s integration ceiling, so there's room to raise the timeout too as
  # extra headroom rather than relying on memory alone.
  memory_size = 3008
  timeout     = 120
}

resource "aws_lambda_function" "sim_aggregator" {
  function_name = "${var.project_name}-sim-aggregator"
  role          = aws_iam_role.sim_aggregator_lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.sim_aggregator.repository_url}:${var.sim_aggregator_image_tag}"
  memory_size   = 256
  timeout       = 30

  environment {
    variables = {
      RESULT_BUCKET = aws_s3_bucket.results.bucket
      RESULT_PREFIX = local.sim_result_prefix
    }
  }
}
