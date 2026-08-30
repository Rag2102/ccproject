# Private bucket the aggregator Lambda writes the simulation's final CSVs
# to. Deliberately separate from the frontend bucket (below) -- this one
# stays fully private (results are downloaded via the AWS CLI/console, not
# served publicly), so there's no risk of a config mistake exposing it via
# CloudFront the way there would be if it shared a bucket with the frontend.

resource "aws_s3_bucket" "results" {
  bucket_prefix = "${var.project_name}-sim-results-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "results" {
  bucket                  = aws_s3_bucket.results.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
