# Three separate repos (rather than one shared image) -- the API, the
# simulation worker, and the aggregator have different dependencies and
# very different sizes (the worker bundles the 198MB VM table; the
# aggregator needs nothing beyond the Lambda base image), so keeping them
# independent means changing one never forces a rebuild/repush of the
# others. See cloud/README.md for the two-phase apply this requires
# (ECR repos must exist and have an image pushed before the Lambda
# resources in lambda.tf can be created).

resource "aws_ecr_repository" "api" {
  name         = "${var.project_name}-api"
  force_delete = true
}

resource "aws_ecr_repository" "sim_worker" {
  name         = "${var.project_name}-sim-worker"
  force_delete = true
}

resource "aws_ecr_repository" "sim_aggregator" {
  name         = "${var.project_name}-sim-aggregator"
  force_delete = true
}

# Every docker push in this project reuses the ":latest" tag (see
# cloud/README.md's push commands), which means each new push doesn't add
# a second tagged image -- it just moves the "latest" tag onto the new
# image and leaves the previous one untagged. Untagged images are exactly
# what quietly build up in ECR (storage cost, no functional purpose once
# orphaned) after every rebuild, so expiring those is what actually does
# the work here. The tagged-image-count rule is a second line of defense
# in case this ever moves to versioned tags instead of a single moving one.
locals {
  ecr_lifecycle_policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep only the 10 most recent tagged images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["latest"]
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = { type = "expire" }
      }
    ]
  })
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy     = local.ecr_lifecycle_policy
}

resource "aws_ecr_lifecycle_policy" "sim_worker" {
  repository = aws_ecr_repository.sim_worker.name
  policy     = local.ecr_lifecycle_policy
}

resource "aws_ecr_lifecycle_policy" "sim_aggregator" {
  repository = aws_ecr_repository.sim_aggregator.name
  policy     = local.ecr_lifecycle_policy
}
