# MOCATRIZ Test 03 · Human Task E2E / Cross-Session Resume

**Objective:** OBJ-MOCATRIZ-002  
**Scenario:** SCN-030  
**Status:** PASS

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

PASS.

Evidence on commit `c188dae6ae3a4a5436922341c183f2d28fec5e13`:
- Landscape Intelligence Schema #201 → SUCCESS.
- SOA Intelligence A2 Persistence Static #73 → SUCCESS.
- Terraform SOA Intelligence DEV Static #145 → SUCCESS.
- SOA Intelligence Worker OCI Runtime Smoke #99 → SUCCESS.
- PR #84 #457 → SUCCESS.
- OCI #257 remained a separate security workstream failure and does not invalidate this Human Task continuity result.

Demonstrated:
- durable WAITING_HUMAN persistence;
- later-session recovery from PostgreSQL rather than conversational memory;
- exact four-part correlation;
- re-entry through UNDERSTAND;
- append-only operational-state evolution;
- fail-closed rejection of wrong-execution correlation.
