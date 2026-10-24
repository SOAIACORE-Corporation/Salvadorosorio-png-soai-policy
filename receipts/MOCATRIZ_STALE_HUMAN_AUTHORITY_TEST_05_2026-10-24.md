# MOCATRIZ Test 05 · Stale Human Authority

**Scenario:** SCN-032  
**Error:** ERR-20261024-033  
**Status:** PASS  
**Validation date:** 2026-10-24

## Claim under test

A correctly correlated human answer must not be accepted after the Human Task has been
revoked, superseded or expired.

## Evidence

Commit:
`e300c0ff971f8e812fc6df3c143a008af9721853`

CI:
- SOA Intelligence A2 Persistence Static #76 → SUCCESS
  - Run A2 persistence contract tests → SUCCESS
  - Enforce no live-cloud boundary → SUCCESS

## Result

PASS.

A SUPERSEDED lifecycle event becomes durable without rewriting the original Human Task.
A later response with all four correlation identifiers correct is rejected fail-closed.

## Canonical consequence

Correlation proves identity. It does not prove that the authorization context is still valid.
