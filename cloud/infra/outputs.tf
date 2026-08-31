output "frontend_url" {
  description = "The live demo -- open this in a browser."
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "api_url" {
  description = "Raw API Gateway invoke URL -- NOT directly callable any more (see waf.tf): only requests carrying the X-Origin-Verify header CloudFront injects get past cloud/api/lambda_function.py's check, so a direct call here now gets a 403. Call the live API through https://<frontend_url>/api/... instead (same-origin, proxied by CloudFront's /api/* behavior); this output is kept for local debugging (curl with a manually-added X-Origin-Verify header) and for `terraform state show` sanity checks."
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

output "alerts_topic_arn" {
  description = "SNS topic every CloudWatch alarm publishes to (observability.tf). Subscribe your own email after applying: aws sns subscribe --topic-arn <this> --protocol email --notification-endpoint you@example.com"
  value       = aws_sns_topic.alerts.arn
}
