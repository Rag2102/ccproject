# ADR-001: AWS is off the critical path

Status: accepted (4 Oct 2026). Open item for the owner: reply on the existing AWS support case; never open a duplicate.

Context: v1 shipped an AWS serverless deployment (`cloud/`). The research result and both papers do not need it, and it can consume light weeks.

Decision: no v2 deliverable depends on AWS. Runs are sharded locally with joblib (Weeks 17-21). The `cloud/` tree stays as v1 and is only touched if it breaks.

Consequences: an AWS outage or support delay cannot block a gate. The Step Functions fan-out may be reused later only by a new ADR.
