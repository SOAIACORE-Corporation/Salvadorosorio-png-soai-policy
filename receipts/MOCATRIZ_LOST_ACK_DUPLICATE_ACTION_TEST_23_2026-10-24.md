# MOCATRIZ Test 23 · Lost Acknowledgement / Duplicate Material Action

**Scenario:** SCN-050  
**Error:** ERR-20261024-050  
**Status:** PASS  
**Validation date:** 2026-10-24

## Claim under test

Loss of the observation channel or process acknowledgement must not cause a material
mutation to be executed twice.

## Defect found

MOCATRIZ already distinguished observability loss from execution failure, but the durable
recovery model had no generic material-action identity/idempotency ledger. After a timeout,
the system could therefore know that outcome was uncertain without having a durable
mechanism to prevent replay.

## Control implemented

A2 migration `1008_mocatriz_material_action_idempotency.sql` adds:

- durable material-action identity;
- project-scoped idempotency key;
- immutable action contract (objective, execution, action type, target, payload hash);
- append-only event history;
- validated state transitions;
- terminal success receipt binding.

Recovery semantics:

- `SUCCEEDED` → `ALREADY_APPLIED`;
- `DISPATCHED` or `INDETERMINATE` → `RECONCILE_REQUIRED`;
- retryable `FAILED` → `RETRY_ALLOWED`;
- same key + different action contract → fail-closed conflict.

## Evidence

Validated head:
`9bb3eed2124cf999887fc09115f0a093525aa980`

CI:
- Landscape Intelligence Schema #273 → SUCCESS
- SOA Intelligence A2 Persistence Static #145 → SUCCESS
  - Run A2 persistence contract tests → SUCCESS
  - Enforce no live-cloud boundary → SUCCESS
- Terraform SOA Intelligence DEV Static #217 → SUCCESS
- SOA Intelligence Alpha Cognitive Loop #80 → SUCCESS
- SOA Intelligence Worker OCI Runtime Smoke #171 → SUCCESS
- PR #84 #541 → SUCCESS

OCI #329 remains a separate security workstream.

## Result

PASS. ERR-20261024-050 is CONTROLLED.

The test demonstrates:
- a durable success cannot be replayed after process/channel loss;
- an unconfirmed dispatched action is reconciled before retry;
- recovery does not append a duplicate execution event;
- an idempotency key cannot silently bind a different payload;
- the complete test uses disposable PostgreSQL and no live external mutation.

## Canonical consequence

> Perder el acuse no autoriza repetir una mutación; antes de reintentar, MOCATRIZ debe demostrar si la acción ya ocurrió.
