# MOCATRIZ Test 24 · Transitive Evidence Invalidation

**Scenario:** SCN-051  
**Error:** ERR-20261024-051  
**Status:** PASS  
**Validation date:** 2026-10-24

## Claim under test

Lineage is insufficient if derived claims, memory and decisions remain CURRENT after a
material dependency becomes stale, superseded, unknown or invalid.

## Defect found

SOAiaCore persisted evidence references, claim evidence, memory lineage and decision
evidence, but no generic control propagated effective validity across those material
dependencies.

## Control implemented

`evaluate_dependency_integrity(...)` computes effective state without rewriting history:

- CURRENT/CONFIRMED/VERIFIED/ADMISSIBLE → CURRENT;
- SUPERSEDED/STALE/UNKNOWN/PARTIAL → REVALIDATION_REQUIRED;
- REJECTED/QUARANTINED → INVALID;
- material dependency state propagates transitively to descendants;
- non-material historical lineage remains preserved but non-blocking;
- dependency cycles fail closed.

## Evidence

Validated head:
`d2c5a620c910fe28b10d7bff8409031a6a2bc8a8`

CI:
- Landscape Intelligence Schema #275 → SUCCESS
- SOA Intelligence A2 Persistence Static #147 → SUCCESS
- Terraform SOA Intelligence DEV Static #219 → SUCCESS
- SOA Intelligence Alpha Cognitive Loop #82 → SUCCESS
- SOA Intelligence Worker OCI Runtime Smoke #173 → SUCCESS
- PR #84 #543 CodeQL actions/javascript-typescript/python → SUCCESS

OCI #331 remains a separate security workstream.

## Result

PASS. ERR-20261024-051 is CONTROLLED.

The test demonstrates:
- stale/superseded/unknown material evidence cannot leave downstream state CURRENT;
- rejected/quarantined evidence invalidates material descendants;
- historical lineage may remain without contaminating new current state;
- replacement current evidence can support a current decision;
- cycles are rejected instead of producing undefined propagation.

## Canonical consequence

> Trazabilidad sin propagación de validez sólo explica de dónde vino una decisión; MOCATRIZ también debe saber cuándo esa decisión necesita dejar de tratarse como vigente.
