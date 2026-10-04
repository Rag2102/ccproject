# ADR-002: The Console is a read-only view and never blocks the paper
Status: accepted
Date: 2026-10-04

Context: The Research Console (v5 Part I section 7) is an artifact, not a scientific claim, and it is the first item cut if time runs short.

Decision: The Console reads frozen `results/summary/*.json` only, shows a provenance badge on every number, and is capped at 16 hours before submission.

Alternatives considered: Make the Console interactive and let it compute results (rejected: a number could differ between the paper and the Console).

Consequences: No result is created or changed in the Console. If it slips, paper A is unaffected.
