# SCN-035 · Concurrent Human Task Isolation

**Class:** MOCATRIZ correlation integrity / concurrency  
**Status:** ACTIVE / TESTABLE  
**Created:** 2026-10-24

## Question

Can SOAiaCore hold multiple WAITING_HUMAN tasks for the same objective while keeping
their executions, responses, resume points and decisions isolated regardless of response
arrival order?

## Test

1. Create task A and task B under the same Objective ID but different Execution IDs,
   Human Task IDs, Correlation IDs and resume points.
2. Persist both.
3. Persist response B first.
4. Persist response A second.
5. Recover both independently.

## PASS

- both tasks remain durable;
- each task receives only its own response;
- arrival order does not influence binding;
- execution A cannot inherit decision B;
- execution B cannot inherit decision A;
- both remain independently resumeable.

## Nullifiers

- global/latest response is used instead of task-scoped response;
- same objective causes response collision;
- one task's resume point or answer appears in the other;
- execution identity is lost during recovery.

## Canonical rule

> Concurrencia no reduce correlación: cada respuesta debe volver a la ejecución exacta que la originó.
