# SCN-050 · Lost Acknowledgement / Duplicate Material Action

**Class:** MOCATRIZ recovery integrity / material-action idempotency  
**Status:** ACTIVE / TESTABLE  
**Created:** 2026-10-24

## Problem

Loss of the observation channel does not prove that a material action failed.

If a mutation is dispatched and the process or channel dies before the acknowledgement is
observed, blindly retrying can apply the same material side effect twice.

## Test

1. Create one durable material-action identity and idempotency key.
2. Persist INTENDED → DISPATCHED → SUCCEEDED with a durable receipt.
3. Lose the process/channel that initiated the action.
4. Start a fresh runtime and request the same action using the same idempotency key.
5. Require ALREADY_APPLIED and no new execution event.
6. Repeat with a second action that is only DISPATCHED and has no terminal receipt.
7. Require RECONCILE_REQUIRED, not retry.
8. Reuse an existing idempotency key with a different payload hash.
9. Require fail-closed idempotency conflict.

## PASS

- known success is never replayed;
- unknown dispatched outcome is reconciled before retry;
- duplicate recovery does not append a second execution;
- same key cannot identify a different mutation;
- no live external system is mutated by the test.

## Nullifiers

- timeout is treated as failure automatically;
- SUCCEEDED action is dispatched again;
- DISPATCHED/unknown action is retried blindly;
- idempotency key can bind a different payload or target;
- state is held only in process memory.

## Canonical rule

> Perder el acuse no autoriza repetir una mutación; antes de reintentar, MOCATRIZ debe demostrar si la acción ya ocurrió.
