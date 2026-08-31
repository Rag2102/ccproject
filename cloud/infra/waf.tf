# AWS WAF, attached to the CloudFront distribution that now serves both
# the static frontend AND (via the /api/* ordered_cache_behavior in
# s3_frontend.tf) the API Gateway HTTP API behind it.
#
# Why this exists instead of API Gateway usage plans + API keys (the
# originally planned approach): API Gateway HTTP APIs (apigatewayv2, what
# this project uses -- see api_gateway.tf) do not support usage plans, API
# keys, or WAF at all; those are REST-API-only features (confirmed against
# AWS's own HTTP-API-vs-REST-API feature comparison). Migrating the whole
# API to a REST API just to unlock them would be a large, risky change to
# an already-working live deployment -- and wouldn't even buy real
# security here, since an API key handed to an anonymous public browser
# demo has to live in public JS, which defeats the point of a "key" in the
# first place (API keys are for identifying backend clients you issue
# credentials to individually, not anonymous public traffic).
#
# What actually fits this architecture: front the API with CloudFront (so
# it's reachable the same way the frontend is) and let WAF do what a
# usage plan would have -- rate-limit and filter traffic -- at the one
# edge point everything now passes through. The shared-secret custom
# header CloudFront attaches to the API origin (see s3_frontend.tf,
# random_password.origin_verify_secret) closes the gap an API key would
# have left open anyway: it stops the raw API Gateway URL from being
# called directly, bypassing WAF entirely.
resource "aws_wafv2_web_acl" "frontend" {
  provider    = aws.us_east_1
  name        = "${var.project_name}-frontend-waf"
  description = "Protects the public demo (static frontend + /api/* proxied to the API Gateway origin) from common web exploits and request floods."
  scope       = "CLOUDFRONT"

  default_action {
    allow {}
  }

  # AWS-managed rule group: SQLi, XSS, and other common exploit signatures.
  # Priced per-request-evaluated, not flat -- see cloud/README.md's cost
  # notes before enabling more managed rule groups than this project needs.
  rule {
    name     = "AWS-AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project_name}-common-rule-set"
      sampled_requests_enabled   = true
    }
  }

  # AWS-managed rule group: known-bad request signatures (exploited CVEs,
  # scanner/bot fingerprints) -- cheap, high-signal, worth the second
  # managed rule group on top of the common set above.
  rule {
    name     = "AWS-AWSManagedRulesKnownBadInputsRuleSet"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project_name}-known-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  # Per-source-IP request cap over a 5-minute sliding window -- this is the
  # real, practical replacement for the per-client throttling a REST API
  # usage plan would have given, applied where it actually matters for an
  # anonymous public demo (by source IP, not by a client-supplied key
  # nobody can keep secret). 2000/5min is generous for a person clicking
  # around the calculator -- comfortably above task 28's existing
  # 10 req/s steady-state API Gateway stage throttle over any realistic
  # 5-minute window -- and a hard stop for a script or bot hammering it.
  rule {
    name     = "RateLimitPerSourceIP"
    priority = 3

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project_name}-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.project_name}-frontend-waf"
    sampled_requests_enabled   = true
  }
}
