# ADR-001: AWS is off the critical path
Status: accepted
Date: 2026-10-04

Context: v1 shipped an AWS serverless deployment (`cloud/`: CloudFront, API Gateway, Lambda, Step Functions). The research result and both papers do not need it, and it can consume light weeks. An existing AWS support case is open; the reply to it is still the owner's to send (never open a duplicate).

Decision: No v2 deliverable depends on AWS. Runs are sharded locally with joblib (weeks 17-21). The `cloud/` tree stays as v1 and is touched only if it breaks.

Alternatives considered: Move the simulator onto the Step Functions fan-out used for the v1 sweep (rejected: adds cost, credentials and a verification dependency to the critical path).

Consequences: An AWS outage or support delay cannot block a gate. The Step Functions fan-out may be reused later only by a new ADR.
