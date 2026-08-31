# The static frontend (cloud/frontend/) -- HTML/CSS/JS + the one PNG chart
# -- served from S3 through CloudFront. No API Gateway/Lambda involved in
# serving any of this: it's plain object storage behind a CDN, which is why
# it's split from the API here rather than the API Lambda also just serving
# these files (see docs/cloud_architecture.md for the rationale).

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

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100" # cheapest edge set -- fine for a demo, not a global product

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "frontend-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
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
  bucket       = aws_s3_bucket.frontend.id
  key          = "config.js"
  content      = templatefile("${path.module}/../frontend/config.js.tpl", { api_base = aws_apigatewayv2_stage.default.invoke_url })
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
