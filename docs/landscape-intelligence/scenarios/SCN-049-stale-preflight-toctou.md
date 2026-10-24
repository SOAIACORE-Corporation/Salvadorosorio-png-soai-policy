# SCN-049 · Stale Preflight / Time-of-Check to Time-of-Use

**Class:** MOCATRIZ execution integrity / preflight freshness  
**Status:** PASS / CONTROLLED  
**Created:** 2026-10-24

## Problem

SCN-029 proves that machine-verifiable prerequisites should be exhausted before asking
for human action. That does not prove those prerequisites remain valid when the material
action is finally executed.

A preflight is a point-in-time claim. Between check and use, authority may expire,
a branch HEAD may move, a policy may change, or an external state may become unknown.

## Test

1. Complete preflight successfully.
2. Preserve one immutable prerequisite.
3. Let an authority grant expire before action time.
4. Change a versioned branch HEAD after preflight.
5. Keep another versioned prerequisite unchanged.
6. Attempt the material action.
7. Require REVALIDATE_REQUIRED and action_authorized=false.
8. Refresh the expired authority and branch version.
9. Require PASS.
10. Present a material prerequisite with no declared freshness basis.
11. Require fail-closed revalidation rather than assuming freshness.

## PASS

- expired time-bounded evidence blocks action;
- changed versioned evidence blocks action;
- immutable evidence remains valid;
- unchanged versioned evidence remains valid;
- unknown freshness blocks action;
- revalidation restores actionability only after current evidence is present.

## Nullifiers

- a historically successful preflight authorizes action indefinitely;
- an expired authority grant remains actionable;
- moved HEAD is ignored;
- missing freshness metadata is treated as current;
- the control invents one universal TTL for all evidence classes.

## Canonical rule

> Un preflight válido demuestra que una condición era cierta al verificarse; antes de una acción material debe seguir siendo demostrablemente vigente.
