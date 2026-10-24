# MOCATRIZ Test 15 · Recovery after Worker / Process Crash

**Scenario:** SCN-042  
**Status:** PASS · CAPABILITY VALIDATED  
**Validation date:** 2026-10-24

## Claim under test

A WAITING_HUMAN execution must survive complete loss of the process that created it and
resume from PostgreSQL without relying on transient Python objects.

## Test boundary

The test intentionally creates two process-loss boundaries:

1. task persisted → original task and Database runtime discarded → fresh Database runtime recovers task;
2. response persisted → recovered bundle/runtime discarded → another fresh Database runtime reconstructs authoritative response.

The response correlation fields are built exclusively from the task recovered after the
first crash boundary.

## Evidence

Validated head:
`f075af451bad3d5fe1aa4a5d318029b64a131067`

CI:
- Landscape Intelligence Schema #245 → SUCCESS
- SOA Intelligence A2 Persistence Static #117 → SUCCESS
- Terraform SOA Intelligence DEV Static #189 → SUCCESS
- SOA Intelligence Alpha Cognitive Loop #52 → SUCCESS
- SOA Intelligence Worker OCI Runtime Smoke #143 → SUCCESS

A2 #117 explicitly passed the disposable PostgreSQL persistence contract tests.

OCI #301 remains a separate security workstream.

## Result

PASS.

No new defect was discovered. The existing durable Human Task architecture survives
process-object loss and can reconstruct task identity, resume point, response authority
and responder provenance from PostgreSQL alone.

## Canonical consequence

> Continuidad real exige que la reanudación pueda reconstruirse desde estado durable después de perder por completo el proceso que lo creó.
