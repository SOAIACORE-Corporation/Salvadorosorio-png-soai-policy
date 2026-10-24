# SCN-032 · Stale Human Authority

**Class:** MOCATRIZ authority integrity / temporal validity  
**Status:** ACTIVE / TESTABLE  
**Detected:** 2026-10-24

## Problem

A human answer can be perfectly correlated and still be unsafe to apply if the Human Task
was revoked, superseded or expired before the answer arrived.

Correlation proves identity. It does not prove current authority.

## Test

1. Persist a WAITING_HUMAN task against checkpoint A.
2. Persist a lifecycle event SUPERSEDED because checkpoint B replaces A.
3. Receive a later response whose Objective ID, Execution ID, Human Task ID and
   Correlation ID all match the original task.
4. Attempt to persist that response.
5. Recover the task bundle.

## PASS

- late response is rejected fail-closed;
- no response becomes authoritative for the stale task;
- original Human Task history remains append-only;
- supersession is represented as a new lifecycle event;
- execution cannot resume from the obsolete checkpoint.

## Nullifiers

- correct correlation alone permits resume;
- original task is rewritten or deleted;
- stale response becomes latest recoverable authority;
- system silently maps authorization from checkpoint A to checkpoint B.

## Canonical rule

> Correlación correcta no implica autoridad vigente.
