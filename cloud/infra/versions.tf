terraform {
  required_version = ">= 1.5"

  # Remote state -- currently local-only (a single laptop is a single
  # point of failure for the only record of ~28 AWS resources, and there's
  # no locking against two applies racing each other). bootstrap/ creates
  # the S3 bucket + DynamoDB lock table this needs.
  #
  # LEFT COMMENTED OUT ON PURPOSE: uncommenting this before the bucket/
  # table exist breaks every terraform command in this directory (init
  # will try to actually reach the literal placeholder bucket name below
  # and fail). Do the migration in its own dedicated pass, not mixed in
  # with unrelated changes:
  #   1. cd bootstrap && terraform init && terraform apply
  #   2. copy its state_bucket / lock_table outputs into the two
  #      placeholders below, then uncomment this block
  #   3. cd .. && terraform init -migrate-state
  #      (answer yes -- this copies the existing local state into the new
  #      backend, it does not touch any real AWS resources)
  #   4. terraform plan -- should report no changes, confirming the
  #      migration didn't lose anything
  #
  # backend "s3" {
  #   bucket         = "REPLACE_WITH_BOOTSTRAP_state_bucket_OUTPUT"
  #   key            = "vm-mitigation/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "REPLACE_WITH_BOOTSTRAP_lock_table_OUTPUT"
  #   encrypt        = true
  # }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    # Used by the frontend CloudFront invalidation in s3_frontend.tf --
    # not previously needed, so `terraform init` must be rerun once to
    # download it before the next `terraform apply`.
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

provider "aws" {
  region = var.aws_region
}
