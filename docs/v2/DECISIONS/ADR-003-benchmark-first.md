# ADR-003: Benchmark-first
Status: accepted
Date: 2026-10-04

Context: Every run should be reusable for VMMBench, not only for paper A.

Decision: Every run writes a `vmmbench/1` record (schema frozen in week 10). Policies see only `Observation` objects. Seed families (dev 101-110, pilot 201-205, eval 1-n, replication 1001+, hidden 9001-9100) are never mixed.

Alternatives considered: Build the experiments first and package a benchmark afterwards (rejected: results would need regenerating in a different format).

Consequences: The same `summary.json` feeds the paper macros, the Console and the leaderboard, so a number cannot differ between them.
