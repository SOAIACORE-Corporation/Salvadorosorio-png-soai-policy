# MOCATRIZ Test 06 · Cross-Project Human Authority Isolation

**Scenario:** SCN-033  
**Error:** ERR-20261024-034  
**Status:** PASS  
**Validation date:** 2026-10-24

## Claim under test

A Human Task response or lifecycle event must not acquire authority merely because its
four correlation identifiers match. Its project_scope must also match the originating task.

## Evidence

Commit:
`34cbf44d6de17d93ac23f06079355ee4459b0607`

CI:
- Landscape Intelligence Schema #206 → SUCCESS
- SOA Intelligence A2 Persistence Static #78 → SUCCESS
  - Run A2 persistence contract tests → SUCCESS
  - Enforce no live-cloud boundary → SUCCESS

## Result

PASS.

Persistence rejects a Project-B response and a Project-B lifecycle event that target a
Project-A Human Task, even when Objective ID, Execution ID, Human Task ID and
Correlation ID are otherwise correct.

## Canonical consequence

Authority has scope. Correct identity without correct scope authorizes nothing.
