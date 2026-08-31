{
  "Comment": "Distributed correlation-sweep simulation (scripts/07_correlated_assignment_experiment.py's per-rho loop, reworked into parallel Lambda invocations -- see cloud/sim/sim_core.py and docs/cloud_architecture.md). Input: {\"trials\": [{\"rho\": <float>, \"seed\": <int>}, ...]} -- see cloud/sim/trials.json for a ready-made 55-trial sweep. Each trial retries transient Lambda/service errors with backoff, and a trial that still fails after retries is marked rather than aborting the other 54 -- see aggregator_lambda_function.py's n_failed_trials handling.",
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
            "Retry": [
              {
                "ErrorEquals": [
                  "Lambda.ServiceException",
                  "Lambda.AWSLambdaException",
                  "Lambda.SdkClientException",
                  "Lambda.TooManyRequestsException"
                ],
                "IntervalSeconds": 2,
                "MaxAttempts": 3,
                "BackoffRate": 2.0
              },
              {
                "ErrorEquals": ["States.Timeout"],
                "IntervalSeconds": 5,
                "MaxAttempts": 2,
                "BackoffRate": 2.0
              }
            ],
            "Catch": [
              {
                "ErrorEquals": ["States.ALL"],
                "ResultPath": "$.error",
                "Next": "MarkTrialFailed"
              }
            ],
            "End": true
          },
          "MarkTrialFailed": {
            "Type": "Pass",
            "Parameters": {
              "trial_failed": true,
              "rho_target.$": "$.rho",
              "seed.$": "$.seed",
              "error.$": "$.error"
            },
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
