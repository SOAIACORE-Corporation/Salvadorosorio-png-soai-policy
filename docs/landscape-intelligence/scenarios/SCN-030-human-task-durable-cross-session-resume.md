# SCN-030 · Human Task durable cross-session resume

**Class:** MOCATRIZ continuity / durable human interaction  
**Status:** ACTIVE / TESTABLE  
**Historical driver:** OBJ-MOCATRIZ-002

## Problem

A Human Task that exists only in process memory does not satisfy MOCATRIZ persistence. The task must survive channel loss, process loss or a later session without depending on ChatGPT memory.

## Preconditions

- Objective has reached a genuine human authority boundary.
- Machine-resolvable preflight has already been exhausted.
- The task contains Objective ID, Execution ID, Human Task ID and Correlation ID.
- A durable A2 PostgreSQL store is available.

## Test sequence

1. Create the Human Task in WAITING_HUMAN.
2. Persist it to `soa_memory.human_tasks`.
3. End the in-memory execution context.
4. Open a later database/session context.
5. Recover the task using only durable state.
6. Persist a separately received human response.
7. Reload the task and response.
8. Correlate all four identifiers.
9. Re-enter through UNDERSTAND.
10. Persist a new operational-state version representing resumed execution.
11. Attempt a wrong-execution response and require fail-closed rejection.

## PASS

PASS requires:
- durable recovery of the task;
- exact correlation;
- correct resume point;
- UNDERSTAND as the recommended re-entry phase;
- append-only state evolution;
- rejection of mismatched response correlation.

## Nullifiers

- Task reconstructed from conversational memory rather than persistence.
- Response binds to the wrong execution.
- Historical WAITING_HUMAN record is overwritten.
- Resume point is lost.
- Human answer is treated as an unconditional command without reinterpretation.
- Test mutates a live/production database.
