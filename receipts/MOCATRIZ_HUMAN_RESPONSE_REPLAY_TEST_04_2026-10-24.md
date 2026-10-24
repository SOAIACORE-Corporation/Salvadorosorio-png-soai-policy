# MOCATRIZ Test 04 · Human Response Replay / Conflicting Decision

**Scenario:** SCN-031  
**Error:** ERR-20261024-032  
**Status:** PASS  
**Validation date:** 2026-10-24

## Claim under test

A durable Human Task must not allow a later replay or conflicting response to silently replace the authoritative human answer used to resume execution.

## Implementation

- migration: `db/a2_migrations/1003_mocatriz_human_response_replay_guard.sql`
- runtime verification: `packages/python-runtime/src/soaiacore_runtime/a2_persistence.py`
- acceptance test: `tests/test_a2_persistence_contract.py::test_human_task_rejects_replay_or_conflicting_second_response`

## Evidence

Commit:
`234f26faf784d643d986f2c2a77c4b2f74909fe0`

CI:
- Landscape Intelligence Schema #202 → SUCCESS
- SOA Intelligence A2 Persistence Static #74 → SUCCESS
  - Run A2 persistence contract tests → SUCCESS
  - Enforce no live-cloud boundary → SUCCESS
- Terraform SOA Intelligence DEV Static #146 → SUCCESS

## Result

PASS.

The first correlated response is durable. A second response with another response_id but the same Objective ID + Execution ID + Human Task ID + Correlation ID is rejected by PostgreSQL. Recovery therefore cannot silently switch to a newer conflicting answer.

## Design consequence

A changed human decision is not represented as an overwrite or a competing response row. It must become a new Human Task or an explicit versioned decision event with its own authority and lineage.
