# ADR-002: The Console is a read-only view and never blocks the paper

Status: accepted (4 Oct 2026).

Context: the Research Console (v3 section 6, v5 Part I section 7) is an artifact, not a scientific claim.

Decision: the Console reads frozen `results/summary/*.json` only, shows a provenance badge on every number, and is capped at 16 hours before submission. It is the first item cut (Part IV cut order).

Consequences: no result is created or changed in the Console; if it slips, Paper A is unaffected.
