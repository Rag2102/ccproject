# One-time bootstrap for Terraform's own remote state backend.
#
# This is a SEPARATE root module with its own small local state file --
# deliberately not part of the main cloud/infra/ config, because you can't
# store that config's state in a bucket the same config's state doesn't
# know exists yet (the classic chicken-and-egg of self-hosting your own
# backend). Apply this once, copy its two outputs into the backend "s3"
# block in ../versions.tf, then run `terraform init -migrate-state` in
# cloud/infra/ to move the existing local state into it.
#
# This bootstrap module's own local state (bootstrap/terraform.tfstate) is
# fine to leave local -- it manages exactly two resources that essentially
# never change once created, so there's nothing to gain from also
# remoting it, and doing so would just recreate the same chicken-and-egg
# problem one level up.

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "vm-mitigation"
}

resource "aws_s3_bucket" "tf_state" {
  bucket_prefix = "${var.project_name}-tfstate-"
  # This bucket holds the only copy of your infrastructure's state once you
  # migrate to it -- force_destroy stays false so `terraform destroy` (run
  # against this bootstrap config, which you should essentially never do)
  # can't casually take it out along with everything else.
  force_destroy = false
}

resource "aws_s3_bucket_versioning" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  versioning_configuration {
    status = "Enabled" # recover a previous state version if a bad apply or manual edit corrupts the latest one
  }
}

resource "aws_s3_bucket_public_access_block" "tf_state" {
  bucket                  = aws_s3_bucket.tf_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Terraform's S3 backend uses this table purely for locking (one item per
# state file, held for the duration of a plan/apply) -- not for storing
# state itself, so on-demand billing is the right call: a few requests a
# month, not worth provisioning read/write capacity for.
resource "aws_dynamodb_table" "tf_lock" {
  name         = "${var.project_name}-tfstate-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}

output "state_bucket" {
  value = aws_s3_bucket.tf_state.bucket
}

output "lock_table" {
  value = aws_dynamodb_table.tf_lock.name
}
