# SCN-034 · Late-Recorded Backdated Revocation

**Class:** MOCATRIZ authority integrity / bitemporal recovery  
**Status:** ACTIVE / TESTABLE  
**Detected:** 2026-10-24

## Problem

A Human Task response can be accepted correctly under the evidence known at T1, while
evidence recorded later at T2 reveals that the task had already been superseded before
the response was received.

Deleting the response would destroy history. Continuing to treat it as current authority
would be false continuity.

## Test

1. Persist a Human Task.
2. Persist a correctly correlated response.
3. Verify that, at the recorded-time boundary before new evidence, the response is authoritative.
4. Later persist a SUPERSEDED lifecycle event whose effective_time precedes the response received_time.
5. Reconstruct current authority.
6. Verify the historical response still exists but is no longer usable for resume.

## PASS

- historical T1 reconstruction still sees the response as authoritative;
- current reconstruction sees it as INVALIDATED;
- response is preserved as evidence;
- resume-facing `response` becomes null/fail-closed;
- invalidating lifecycle lineage is explicit.

## Nullifiers

- late evidence deletes or rewrites the response;
- current recovery continues to resume from the invalidated answer;
- past-state reconstruction is rewritten by later knowledge;
- narrative logic, rather than temporal evidence, decides validity.

## Canonical rule

> Nueva evidencia puede invalidar autoridad vigente sin reescribir lo que históricamente se sabía.
