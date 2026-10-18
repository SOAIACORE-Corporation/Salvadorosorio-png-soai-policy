# MOCATRIZ Test 03 · Human Task E2E / Cross-Session Resume

**Objective:** OBJ-MOCATRIZ-002  
**Scenario:** SCN-030  
**Status:** PENDING CI VALIDATION

## Claim under test

SOAiaCore can persist a Human Task at WAITING_HUMAN, lose the transient execution context, recover the task from durable storage, bind only the correct human response, reinterpret it through UNDERSTAND and resume the correct execution from its persisted resume point.

## Persistence boundary

The acceptance test uses the disposable PostgreSQL service provided by GitHub Actions. It does not write Azure PostgreSQL or any production database.

## Required evidence

- migration `1002_mocatriz_human_task_resume.sql`;
- durable task table;
- durable response table;
- append-only triggers;
- four-part composite correlation FK;
- cross-session acceptance test;
- resumed operational_state version;
- fail-closed wrong-correlation test;
- successful A2 Persistence and Landscape CI.

## Result

Pending current HEAD CI. This receipt must be updated only after terminal workflow evidence exists.
