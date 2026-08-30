output "frontend_url" {
  description = "The live demo -- open this in a browser."
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "api_url" {
  description = "API Gateway invoke URL the frontend calls (also baked into cloud/frontend's generated config.js)."
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "ecr_api_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "ecr_sim_worker_repository_url" {
  value = aws_ecr_repository.sim_worker.repository_url
}

output "ecr_sim_aggregator_repository_url" {
  value = aws_ecr_repository.sim_aggregator.repository_url
}

output "sim_state_machine_arn" {
  description = "Pass this to `aws stepfunctions start-execution` (see cloud/README.md) to run the distributed simulation."
  value       = aws_sfn_state_machine.sim.arn
}

output "sim_results_bucket" {
  description = "Where the aggregator Lambda writes the sweep's output CSVs/JSON after a Step Functions execution completes."
  value       = aws_s3_bucket.results.bucket
}
