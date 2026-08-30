variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix used for naming every resource this creates."
  type        = string
  default     = "vm-mitigation"
}

variable "api_image_tag" {
  description = "Tag of the API Lambda image already pushed to its ECR repo (see cloud/README.md -- build+push happens before this variable's value matters)."
  type        = string
  default     = "latest"
}

variable "sim_worker_image_tag" {
  description = "Tag of the simulation-worker Lambda image already pushed to its ECR repo."
  type        = string
  default     = "latest"
}

variable "sim_aggregator_image_tag" {
  description = "Tag of the simulation-aggregator Lambda image already pushed to its ECR repo."
  type        = string
  default     = "latest"
}

variable "sim_map_concurrency" {
  description = "Max concurrent Lambda invocations the Step Functions Map state runs at once. Keeps this a friendly, cheap demo rather than a burst that trips Lambda's default concurrency limit."
  type        = number
  default     = 10
}
