# MOCATRIZ Test 09 · Human Response Provenance Gate

**Scenario:** SCN-036  
**Error:** ERR-20261024-037  
**Status:** PASS  
**Validation date:** 2026-10-24

## Claim under test

A correctly correlated Human Task answer is not durable authority unless the persisted
response also preserves responder identity, authority level and a reference to upstream
authentication evidence.

## Evidence

Commit:
`f3bc0fc87c0a87a2ff777e517e2bf9ce1f00b048`

CI:
- Landscape Intelligence Schema #210 → SUCCESS
- SOA Intelligence A2 Persistence Static #82 → SUCCESS
- Terraform SOA Intelligence DEV Static #154 → SUCCESS
- SOA Intelligence Worker OCI Runtime Smoke #108 → SUCCESS
- SOA Intelligence Alpha Cognitive Loop #17 → SUCCESS
- CodeQL JavaScript/TypeScript → SUCCESS
- CodeQL Actions → SUCCESS
- CodeQL Python → SUCCESS

OCI #266 remains a separate security workstream and does not change this result.

## Result

PASS.

A response with correct task correlation but missing provenance is rejected by PostgreSQL.
A response containing `responder_ref`, `authority_level` and `authentication_ref`
is persisted and those fields survive durable recovery.

## Boundary

The test proves durable provenance requirements. It does not prove that the database
cryptographically authenticated the human. `authentication_ref` must point to upstream
identity/authentication evidence.

## Canonical consequence

Correlation identifies the task. Provenance supports the claim that an authorized human
actually supplied the answer.
