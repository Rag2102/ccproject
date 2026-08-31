# HTTP API (cheaper and simpler than a REST API) with a single Lambda proxy
# integration behind a catch-all route -- app.py's own Flask routing (via
# cloud/api/lambda_function.py's WSGI adapter) decides what each path does,
# so API Gateway itself just needs to hand every request through.

resource "aws_apigatewayv2_api" "api" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"

  # Mostly vestigial since s3_frontend.tf started proxying /api/* through
  # the same CloudFront distribution the frontend is served from: same-
  # origin requests don't trigger a CORS preflight in the first place, so
  # the frontend no longer actually depends on this. Left in place (harmless
  # either way) as a safety net for anyone hitting the raw API Gateway
  # invoke_url directly during local debugging with the origin-verify
  # header manually added (see waf.tf, cloud/api/lambda_function.py).
  cors_configuration {
    # Scoped to the actual CloudFront frontend rather than "*" -- this is a
    # live reference (not a hardcoded domain), so it can never drift: if the
    # distribution is ever destroyed and recreated, its domain changes and
    # this updates automatically on the next apply. Note this does make the
    # API's CORS config depend on the CloudFront distribution existing --
    # see s3_frontend.tf for that resource.
    allow_origins = ["https://${aws_cloudfront_distribution.frontend.domain_name}"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["content-type"]
  }
}

resource "aws_apigatewayv2_integration" "api" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.api.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true

  # Nothing stopped a runaway client loop (or plain abuse) from hammering
  # this endpoint and running up the Lambda bill -- there was no ceiling
  # of any kind. These numbers are generous for a demo (comfortably above
  # what a few people clicking around the live calculator would ever hit)
  # but stop the unbounded case. Tune upward if a real audience needs it.
  default_route_settings {
    throttling_burst_limit = 20
    throttling_rate_limit  = 10
  }
}

resource "aws_lambda_permission" "api_gateway_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}
