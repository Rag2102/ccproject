# ADR-003: Benchmark-first

Status: accepted (4 Oct 2026).

Context: every run should be reusable for VMMBench, not only for Paper A.

Decision: every run writes a `vmmbench/1` record (schema frozen in Week 10). Policies see only `Observation` objects. Seed families (dev 101-110, pilot 201-205, eval 1-n, replication 1001+, hidden 9001-9100) are never mixed.

Consequences: the same `summary.json` feeds the paper macros, the Console and the leaderboard, so a number cannot differ between them.
