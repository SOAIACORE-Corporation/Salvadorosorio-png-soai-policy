# SCN-031 · Human Response Replay / Conflicting Decision

**Class:** MOCATRIZ authority integrity / durable human interaction  
**Status:** ACTIVE / TESTABLE  
**Detected:** 2026-10-24

## Problem

SCN-030 proves durable recovery and correct four-part correlation, but the original
response table permits more than one response row for the same Human Task. The loader
selects the latest response, so a replay or later conflicting answer could silently
change the evidence used to resume an execution.

## Test

1. Persist a WAITING_HUMAN task.
2. Persist the first correctly correlated human response.
3. Attempt a second response with a different response_id but the same
   Objective ID + Execution ID + Human Task ID + Correlation ID.
4. Make the second answer conflict with the first.
5. Reload the durable bundle.

## PASS

- the first response persists;
- the second response is rejected fail-closed by persistence;
- the original response remains the authoritative response used for recovery;
- no UPDATE/DELETE is used;
- a changed decision requires a new task or decision event.

## Nullifiers

- loader silently selects a later conflicting response;
- first response can be overwritten;
- duplicate/replay becomes effective because it has a newer timestamp;
- test requires production database mutation.

## Design rule

> Durable human authority must be replay-safe. Append-only history does not permit
> a later row to silently redefine which answer authorized the resume.
