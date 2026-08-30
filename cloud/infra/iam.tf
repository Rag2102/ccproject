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

resource "aws_iam_role_policy_attachment" "api_lambda_basic" {
  role       = aws_iam_role.api_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# --- Simulation worker Lambda: logs only. Data is baked into its image too. ---
resource "aws_iam_role" "sim_worker_lambda" {
  name               = "${var.project_name}-sim-worker-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "sim_worker_lambda_basic" {
  role       = aws_iam_role.sim_worker_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# --- Aggregator Lambda: logs + write access to the results bucket only
# (not read/list/delete -- it only ever needs to put 3 known keys). ---
resource "aws_iam_role" "sim_aggregator_lambda" {
  name               = "${var.project_name}-sim-aggregator-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "sim_aggregator_lambda_basic" {
  role       = aws_iam_role.sim_aggregator_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
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
