# The static frontend (cloud/frontend/) -- HTML/CSS/JS + the one PNG chart
# -- served from S3 through CloudFront. No API Gateway/Lambda involved in
# serving any of this: it's plain object storage behind a CDN, which is why
# it's split from the API here rather than the API Lambda also just serving
# these files (see docs/cloud_architecture.md for the rationale).
#
# This distribution also fronts the API Gateway HTTP API itself (the
# ordered_cache_behavior for /api/* below) -- see waf.tf's comment for why:
# HTTP APIs can't take a usage plan, an API key, or WAF directly, so
# putting CloudFront in front of it is what makes WAF (and same-origin
# calls from the frontend, removing the need for CORS) possible at all.

resource "aws_s3_bucket" "frontend" {
  bucket_prefix = "${var.project_name}-frontend-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${var.project_name}-frontend-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# A secret only CloudFront knows, injected as a custom header on every
# request CloudFront forwards to the API origin below. cloud/api/
# lambda_function.py checks it and returns 403 to anything that doesn't
# have it -- i.e. anyone calling the raw API Gateway invoke_url directly,
# bypassing CloudFront (and therefore bypassing WAF too). This is the
# standard AWS-recommended pattern for restricting a custom origin to one
# specific CloudFront distribution when the origin type itself has no
# native way to check "did this request really come from my CDN" (API
# Gateway HTTP APIs don't support resource policies or OAC the way S3
# does). Not secret from AWS itself (it lives in Terraform state and the
# Lambda's environment variables, like any other generated credential) --
# secret from the public internet, which is the actual threat model here.
resource "random_password" "origin_verify_secret" {
  length  = 32
  special = false
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100" # cheapest edge set -- fine for a demo, not a global product
  web_acl_id          = aws_wafv2_web_acl.frontend.arn

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "frontend-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  # The API Gateway HTTP API's own default endpoint, reached only through
  # this distribution (see the origin-verify secret above). api_endpoint
  # already includes the https:// scheme CloudFront's domain_name field
  # doesn't want, hence the replace().
  origin {
    domain_name = replace(aws_apigatewayv2_api.api.api_endpoint, "https://", "")
    origin_id   = "api-gateway"

    custom_origin_config {
      http_port                = 80
      https_port                = 443
      origin_protocol_policy    = "https-only"
      origin_ssl_protocols      = ["TLSv1.2"]
      # Matches the API Lambda's own 30s timeout (lambda.tf) -- explicit
      # rather than relying on CloudFront's default so the two ceilings
      # can't silently drift apart.
      origin_read_timeout       = 30
      origin_keepalive_timeout  = 5
    }

    custom_header {
      name  = "X-Origin-Verify"
      value = random_password.origin_verify_secret.result
    }
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "frontend-s3"
    viewer_protocol_policy = "redirect-to-https"
    compress                = true
    # Defer to each object's own Cache-Control header (set below) instead
    # of CloudFront's implicit default (~24h) -- that default is exactly
    # why a redeploy of index.html/app.js could sit stale at the edge for
    # up to a day with no visible error. max_ttl is a safety ceiling in
    # case an object is ever uploaded without a Cache-Control header.
    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 86400

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
  }

  # /api/meta and /api/predict proxy straight through to the API Gateway
  # origin above -- same path, no rewriting, since webapp/app.py's own
  # Flask routes already include the /api prefix (see cloud/api/
  # lambda_function.py's docstring: the Lambda wraps that same Flask app
  # unchanged). Never cached: every response here is either live model
  # inference or reference data that can change on the next deploy: the
  # API's own JSON body is the source of truth, not the edge.
  ordered_cache_behavior {
    path_pattern            = "/api/*"
    allowed_methods         = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods          = ["GET", "HEAD"]
    target_origin_id        = "api-gateway"
    viewer_protocol_policy  = "https-only"
    compress                = true
    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0

    forwarded_values {
      query_string = true
      headers      = ["Content-Type", "Accept"]
      cookies {
        forward = "none"
      }
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

data "aws_iam_policy_document" "frontend_bucket_policy" {
  statement {
    sid       = "AllowCloudFrontRead"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.frontend.arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.frontend.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = data.aws_iam_policy_document.frontend_bucket_policy.json
}

# --- Static assets: index.html + app.js as-is, config.js generated with the
# real API Gateway URL, and every PNG under docs/figures/. ---

resource "aws_s3_object" "index_html" {
  bucket       = aws_s3_bucket.frontend.id
  key          = "index.html"
  source       = "${path.module}/../frontend/index.html"
  etag         = filemd5("${path.module}/../frontend/index.html")
  content_type = "text/html"
  cache_control = "no-cache"
}

resource "aws_s3_object" "app_js" {
  bucket       = aws_s3_bucket.frontend.id
  key          = "app.js"
  source       = "${path.module}/../frontend/app.js"
  etag         = filemd5("${path.module}/../frontend/app.js")
  content_type = "application/javascript"
  cache_control = "no-cache"
}

resource "aws_s3_object" "config_js" {
  bucket = aws_s3_bucket.frontend.id
  key    = "config.js"
  # api_base is now "" (same origin) rather than the raw API Gateway invoke
  # URL: the frontend and API are both served from this one CloudFront
  # distribution (the /api/* ordered_cache_behavior above), so app.js's
  # `${window.API_BASE}/api/predict` resolves to a same-origin, relative
  # request. This also means the frontend no longer depends on API Gateway
  # CORS working correctly -- a same-origin request never triggers a
  # preflight in the first place.
  content      = templatefile("${path.module}/../frontend/config.js.tpl", { api_base = "" })
  content_type = "application/javascript"
  cache_control = "no-cache"
}

resource "aws_s3_object" "figures" {
  for_each      = fileset("${path.module}/../../docs/figures", "*.png")
  bucket        = aws_s3_bucket.frontend.id
  key           = "figures/${each.value}"
  source        = "${path.module}/../../docs/figures/${each.value}"
  etag          = filemd5("${path.module}/../../docs/figures/${each.value}")
  content_type  = "image/png"
  cache_control = "public, max-age=86400"
}
# no-cache on the objects above means CloudFront always revalidates against
# S3 -- correct, but still one round-trip behind a truly instant update.
# This forces an edge invalidation on the same apply whenever one of the
# three dynamic files actually changes, so `terraform apply` alone is
# enough to make a frontend edit visible immediately.
resource "null_resource" "frontend_invalidation" {
  triggers = {
    index_html = aws_s3_object.index_html.etag
    app_js     = aws_s3_object.app_js.etag
    config_js  = md5(aws_s3_object.config_js.content)
  }

  provisioner "local-exec" {
    command = "aws cloudfront create-invalidation --distribution-id ${aws_cloudfront_distribution.frontend.id} --paths '/*'"
  }
}
