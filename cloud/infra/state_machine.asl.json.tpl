{
  "Comment": "Distributed correlation-sweep simulation (scripts/07_correlated_assignment_experiment.py's per-rho loop, reworked into parallel Lambda invocations -- see cloud/sim/sim_core.py and docs/cloud_architecture.md). Input: {\"trials\": [{\"rho\": <float>, \"seed\": <int>}, ...]} -- see cloud/sim/trials.json for a ready-made 55-trial sweep.",
  "StartAt": "SimulateTrials",
  "States": {
    "SimulateTrials": {
      "Type": "Map",
      "ItemsPath": "$.trials",
      "MaxConcurrency": ${max_concurrency},
      "ItemProcessor": {
        "ProcessorConfig": {
          "Mode": "INLINE"
        },
        "StartAt": "InvokeWorker",
        "States": {
          "InvokeWorker": {
            "Type": "Task",
            "Resource": "${worker_arn}",
            "End": true
          }
        }
      },
      "ResultPath": "$.trial_results",
      "Next": "Aggregate"
    },
    "Aggregate": {
      "Type": "Task",
      "Resource": "${aggregator_arn}",
      "InputPath": "$.trial_results",
      "End": true
    }
  }
}
