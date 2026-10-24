# SCN-033 · Cross-Project Human Authority Isolation

**Class:** MOCATRIZ authority integrity / project isolation  
**Status:** ACTIVE / TESTABLE  
**Detected:** 2026-10-24

## Problem

Human Task correlation originally bound Objective ID + Execution ID + Human Task ID +
Correlation ID, but the foreign keys did not include `project_scope`.

That permits a structurally correlated response or lifecycle event to declare another
project unless persistence enforces scope equality.

## Test

1. Persist a WAITING_HUMAN task in Project-A.
2. Attempt a correctly correlated response under Project-B.
3. Attempt a correctly correlated REVOKED lifecycle event under Project-B.
4. Reload the Project-A task.

## PASS

- Project-B response is rejected by persistence;
- Project-B lifecycle event is rejected;
- Project-A remains unanswered and unmodified;
- project_scope becomes part of durable authority correlation.

## Nullifiers

- same four IDs allow cross-project response insertion;
- another project can revoke/supersede a task it does not own;
- application-layer filtering is the only isolation control.

## Canonical rule

> La autoridad correlacionada también tiene ámbito. Identidad correcta sin scope correcto no autoriza nada.
