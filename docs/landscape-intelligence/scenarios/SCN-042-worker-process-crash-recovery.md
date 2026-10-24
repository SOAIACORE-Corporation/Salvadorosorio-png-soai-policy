# SCN-042 · Recovery after Worker / Process Crash

**Class:** MOCATRIZ durable recovery / process-loss continuity  
**Status:** ACTIVE / TESTABLE  
**Created:** 2026-10-24

## Problem

Cross-session persistence is not fully demonstrated if the test still reuses the same
runtime object or transient Python variables that existed before persistence.

A process crash must be survivable from durable evidence alone.

## Test

1. Create and persist a WAITING_HUMAN task in ephemeral PostgreSQL.
2. Discard the in-memory task object and the original Database runtime object.
3. Instantiate a fresh Database runtime using only the durable connection reference.
4. Recover the Human Task using only project_scope + human_task_id.
5. Build the human response correlation fields exclusively from the recovered durable task.
6. Persist the response.
7. Discard that runtime and instantiate another fresh runtime.
8. Recover again and require AUTHORITATIVE response, preserved provenance, and the original resume point.

## PASS

- no transient task object is needed after the crash boundary;
- fresh runtime instances reconstruct the exact task from PostgreSQL;
- response correlation can be rebuilt from recovered durable state;
- authority/provenance survive a second process-loss boundary;
- no live-cloud mutation is involved.

## Canonical rule

> Continuidad real exige que la reanudación pueda reconstruirse desde estado durable después de perder por completo el proceso que lo creó.
