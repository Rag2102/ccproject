# CloudWatch alarms for the pieces of this architecture that can fail
# silently otherwise: the API Lambda erroring or creeping toward its 30s
# hard timeout, a burst of 5xx at API Gateway, or a distributed-simulation
# Step Functions execution actually failing. Paired with the structured
# JSON logging webapp/core.py now emits (docs/observability.md) -- an
# alarm says *that* something's wrong; CloudWatch Logs Insights on those
# JSON lines is how you'd find out *what* was being requested when it did.
#
# Every alarm publishes to one SNS topic. Terraform creates the topic but
# deliberately does NOT subscribe an email to it -- that would mean
# hardcoding a personal email address into version-controlled
# infrastructure code. Subscribe yourself after the first apply:
#   aws sns subscribe --topic-arn "$(terraform output -raw alerts_topic_arn)" \
#     --protocol email --notification-endpoint you@example.com
# (then confirm the email AWS sends you -- SNS email subscriptions stay
# "pending confirmation" and silent until you click that link).
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts"
}

# --- API Lambda: unhandled errors, throttling, and duration creeping
# toward the 30s API Gateway integration ceiling -- lambda.tf's own
# comment already documents this exact failure mode (intermittent 503s
# before memory was bumped to 3008MB); this is what would catch it coming
# back, or a regression that makes cold starts slow again. ---
resource "aws_cloudwatch_metric_alarm" "api_lambda_errors" {
  alarm_name          = "${var.project_name}-api-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods   = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "The API Lambda (webapp/core.py + app.py, invoked on every /api/predict and /api/meta call) threw an unhandled exception in the last 5 minutes."
  treat_missing_data  = "notBreaching"
  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_lambda_throttles" {
  alarm_name          = "${var.project_name}-api-lambda-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods   = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "The API Lambda is being throttled (concurrent executions exceeded the function/account limit) -- some requests are failing outright, not just queuing."
  treat_missing_data  = "notBreaching"
  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_lambda_duration_near_timeout" {
  alarm_name          = "${var.project_name}-api-lambda-duration-near-timeout"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods   = 1
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  extended_statistic  = "p99"
  threshold           = 25000 # ms -- 5s of headroom before the 30s hard timeout (lambda.tf's comment)
  alarm_description   = "p99 API Lambda duration is within 5s of its 30s timeout (also API Gateway HTTP API's own hard integration ceiling) -- real risk of timeouts, the same failure mode 3008MB of memory was meant to fix."
  treat_missing_data  = "notBreaching"
  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
}

# --- API Gateway: a burst of 5xx. Deliberately NOT alarming on 4xx --
# webapp/core.py's input validation (task 40) makes a 400 an expected,
# routine response to a malformed request, not an incident; alarming on
# it would just be noise every time someone fat-fingers the demo form. ---
resource "aws_cloudwatch_metric_alarm" "api_gateway_5xx" {
  alarm_name          = "${var.project_name}-api-gateway-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods   = 1
  metric_name         = "5xx"
  namespace           = "AWS/ApiGateway"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "API Gateway returned one or more 5xx responses in the last 5 minutes -- check api_lambda_errors/api_lambda_duration_near_timeout first, since those are the most likely cause."
  treat_missing_data  = "notBreaching"
  dimensions = {
    ApiId = aws_apigatewayv2_api.api.id
    Stage = aws_apigatewayv2_stage.default.name
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
}

# --- Distributed simulation: a Step Functions execution actually failing
# (not the same thing as a single trial's worker Lambda erroring inside a
# Map iteration -- Retry/Catch, added earlier, absorbs most of those; this
# is for when the whole execution comes back FAILED). ---
resource "aws_cloudwatch_metric_alarm" "sim_execution_failures" {
  alarm_name          = "${var.project_name}-sim-execution-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods   = 1
  metric_name         = "ExecutionsFailed"
  namespace           = "AWS/States"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "A Step Functions execution of the distributed correlation-sweep simulation failed. Check with: aws stepfunctions describe-execution --execution-arn <arn>"
  treat_missing_data  = "notBreaching"
  dimensions = {
    StateMachineArn = aws_sfn_state_machine.sim.arn
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
}
