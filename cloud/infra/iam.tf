data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# --- API Lambda: logs only. No S3/other access needed -- models and
# reference data are baked into its container image. ---
resource "aws_iam_role" "api_lambda" {
  name               = "${var.project_name}-api-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

# A custom policy scoped to exactly this function's own log group, instead
# of the AWS-managed AWSLambdaBasicExecutionRole -- convenient, but it
# grants logs:CreateLogGroup/CreateLogStream/PutLogEvents on
# arn:aws:logs:*:*:* (every log group in the whole account, not just this
# project's). This function's log group already exists as a Terraform
# resource with its own retention policy (lambda.tf's aws_cloudwatch_
# log_group.api), so logs:CreateLogGroup isn't even needed here -- the one
# thing left to grant is writing into that specific, already-created group.
data "aws_iam_policy_document" "api_lambda_logs" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.api.arn}:*"]
  }
}

resource "aws_iam_role_policy" "api_lambda_logs" {
  name   = "${var.project_name}-api-lambda-logs"
  role   = aws_iam_role.api_lambda.id
  policy = data.aws_iam_policy_document.api_lambda_logs.json
}

# --- Simulation worker Lambda: logs only. Data is baked into its image too. ---
resource "aws_iam_role" "sim_worker_lambda" {
  name               = "${var.project_name}-sim-worker-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

# Same reasoning as api_lambda_logs above: scoped to this function's own
# already-created log group rather than the account-wide managed policy.
data "aws_iam_policy_document" "sim_worker_lambda_logs" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.sim_worker.arn}:*"]
  }
}

resource "aws_iam_role_policy" "sim_worker_lambda_logs" {
  name   = "${var.project_name}-sim-worker-lambda-logs"
  role   = aws_iam_role.sim_worker_lambda.id
  policy = data.aws_iam_policy_document.sim_worker_lambda_logs.json
}

# --- Aggregator Lambda: logs + write access to the results bucket only
# (not read/list/delete -- it only ever needs to put 3 known keys). ---
resource "aws_iam_role" "sim_aggregator_lambda" {
  name               = "${var.project_name}-sim-aggregator-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

# Same reasoning as api_lambda_logs above: scoped to this function's own
# already-created log group rather than the account-wide managed policy.
data "aws_iam_policy_document" "sim_aggregator_lambda_logs" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.sim_aggregator.arn}:*"]
  }
}

resource "aws_iam_role_policy" "sim_aggregator_lambda_logs" {
  name   = "${var.project_name}-sim-aggregator-lambda-logs"
  role   = aws_iam_role.sim_aggregator_lambda.id
  policy = data.aws_iam_policy_document.sim_aggregator_lambda_logs.json
}

data "aws_iam_policy_document" "sim_aggregator_s3_write" {
  statement {
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.results.arn}/${local.sim_result_prefix}/*"]
  }
}

resource "aws_iam_role_policy" "sim_aggregator_s3_write" {
  name   = "${var.project_name}-sim-aggregator-s3-write"
  role   = aws_iam_role.sim_aggregator_lambda.id
  policy = data.aws_iam_policy_document.sim_aggregator_s3_write.json
}

# --- Step Functions: only needs to invoke the two simulation Lambdas. ---
data "aws_iam_policy_document" "states_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sim_state_machine" {
  name               = "${var.project_name}-sim-state-machine"
  assume_role_policy = data.aws_iam_policy_document.states_assume_role.json
}

data "aws_iam_policy_document" "sim_state_machine_invoke" {
  statement {
    actions = ["lambda:InvokeFunction"]
    resources = [
      aws_lambda_function.sim_worker.arn,
      aws_lambda_function.sim_aggregator.arn,
    ]
  }
}

resource "aws_iam_role_policy" "sim_state_machine_invoke" {
  name   = "${var.project_name}-sim-state-machine-invoke"
  role   = aws_iam_role.sim_state_machine.id
  policy = data.aws_iam_policy_document.sim_state_machine_invoke.json
}
