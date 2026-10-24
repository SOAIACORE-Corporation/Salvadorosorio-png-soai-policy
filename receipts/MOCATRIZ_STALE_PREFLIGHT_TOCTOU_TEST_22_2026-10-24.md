# MOCATRIZ Test 22 · Stale Preflight / Time-of-Check to Time-of-Use

**Scenario:** SCN-049  
**Error:** ERR-20261024-049  
**Status:** PASS  
**Validation date:** 2026-10-24

## Claim under test

A preflight that was correct when performed does not authorize a later material action
unless its material prerequisites are still demonstrably current.

## Defect found

SCN-029 proved preflight completeness but did not model freshness between the moment of
validation and the moment of use. An expired authority grant, moved branch HEAD or
unknown freshness basis could therefore be treated as if the earlier validation were
still sufficient.

## Control implemented

`evaluate_preflight_freshness(...)` now requires explicit freshness semantics for
material prerequisites:

- `IMMUTABLE` — content-addressed / intrinsically stable evidence;
- `VALID_UNTIL` — time-bounded evidence;
- `VERSIONED` — observed version must equal current version.

Any expired, changed or freshness-unknown material prerequisite produces:

`REVALIDATE_REQUIRED`

and:

`action_authorized=false`

The control intentionally does not impose one universal TTL.

## Evidence

Validated head:
`9e5001b60e65e76dc2cc43d63aa1b789db75eb56`

CI:
- Landscape Intelligence Schema #271 → SUCCESS
- SOA Intelligence A2 Persistence Static #143 → SUCCESS
- Terraform SOA Intelligence DEV Static #215 → SUCCESS
- SOA Intelligence Alpha Cognitive Loop #78 → SUCCESS
- SOA Intelligence Worker OCI Runtime Smoke #169 → SUCCESS
- PR #84 #539 → SUCCESS

OCI #327 remains a separate security workstream.

## Result

PASS. ERR-20261024-049 is CONTROLLED.

The tests prove:
- expired time-bounded evidence blocks action;
- changed versioned evidence blocks action;
- immutable evidence remains valid;
- unchanged versioned evidence remains valid;
- missing freshness semantics fail closed;
- refreshed current evidence restores actionability.

## Canonical consequence

> Un preflight válido demuestra que una condición era cierta al verificarse; antes de una acción material debe seguir siendo demostrablemente vigente.
