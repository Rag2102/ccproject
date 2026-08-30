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
