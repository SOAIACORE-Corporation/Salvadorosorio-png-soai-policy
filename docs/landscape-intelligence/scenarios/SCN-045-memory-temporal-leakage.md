# SCN-045 · Memory Temporal Leakage

**Class:** MOCATRIZ bitemporal integrity / historical knowledge boundary  
**Status:** ACTIVE / TESTABLE  
**Created:** 2026-10-24

## Problem

A historical query must reconstruct what was knowable at the requested record-time, not
what the system learned later.

The SQL contract structurally applies `recorded_time <= p_recorded_at` across canonical
memory, episodic memory, operational state and decision state. The adversarial requirement
is to prove that the rule holds end-to-end across all four surfaces.

## Test

1. Persist T1 versions/events with record-time in January.
2. Persist T2 versions/events with record-time in February while keeping the same valid-time.
3. Query all four surfaces with valid-time in January and recorded_at in January.
4. Require only T1 to be visible.
5. Query again with the same valid-time but recorded_at in February.
6. Require T2 to become visible.
7. No future-recorded fact may leak backward into the T1 knowledge boundary.

## PASS

- canonical memory does not leak T2 into T1;
- episodic memory does not leak T2 into T1;
- operational state does not leak T2 into T1;
- decision state does not leak T2 into T1;
- the same valid-time can legitimately yield different answers as record-time advances.

## Canonical rule

> Una consulta histórica reconstruye lo que podía saberse entonces; conocimiento registrado después no puede viajar hacia atrás en record-time.
