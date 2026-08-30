# The distributed-compute piece: a Map state fans out over every (rho, seed)
# trial, invoking the worker Lambda concurrently for each (bounded by
# var.sim_map_concurrency so this stays a cheap, well-behaved demo rather
# than a burst that trips Lambda's account-level concurrency limit), then
# feeds every result into the aggregator Lambda in one final step.
#
# To run it: aws stepfunctions start-execution --state-machine-arn <arn>
# --input file://cloud/sim/trials.json  (see cloud/README.md).

resource "aws_sfn_state_machine" "sim" {
  name     = "${var.project_name}-sim"
  role_arn = aws_iam_role.sim_state_machine.arn

  definition = templatefile("${path.module}/state_machine.asl.json.tpl", {
    worker_arn      = aws_lambda_function.sim_worker.arn
    aggregator_arn  = aws_lambda_function.sim_aggregator.arn
    max_concurrency = var.sim_map_concurrency
  })
}
