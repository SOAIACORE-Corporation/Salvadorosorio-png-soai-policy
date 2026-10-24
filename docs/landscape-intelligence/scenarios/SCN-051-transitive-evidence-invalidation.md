# SCN-051 · Transitive Evidence Invalidation

**Class:** MOCATRIZ epistemic integrity / dependency propagation  
**Status:** PASS / CONTROLLED  
**Created:** 2026-10-24

## Problem

SOAiaCore stores evidence, claims, memory lineage and decision evidence. Lineage alone does
not prove that derived state remains valid when a material dependency later becomes
SUPERSEDED, STALE, UNKNOWN, QUARANTINED or REJECTED.

A historically correct decision may remain part of history while no longer being safe to
present as current.

## Test

1. Build material dependency chain evidence → claim → canonical memory → decision.
2. Mark the evidence SUPERSEDED.
3. Require REVALIDATION_REQUIRED to propagate transitively through all material descendants.
4. Repeat with REJECTED evidence.
5. Require INVALID to propagate through material descendants.
6. Preserve an old superseded evidence link as non-material historical lineage while a
   new ADMISSIBLE evidence item materially supports the current decision.
7. Require the new decision to remain CURRENT.
8. Present UNKNOWN material evidence.
9. Require fail-closed revalidation.
10. Introduce a dependency cycle.
11. Require explicit rejection rather than undefined propagation.

## PASS

- stale/superseded/unknown material evidence cannot leave descendants CURRENT;
- rejected/quarantined evidence invalidates material descendants;
- historical lineage may remain without contaminating current state when it is non-material;
- replacement current evidence can support a new current decision;
- cycles fail closed;
- historical nodes are not mutated or deleted by the evaluator.

## Nullifiers

- lineage is informational only and derived decisions stay CURRENT after material evidence becomes stale;
- UNKNOWN is treated as healthy;
- REJECTED evidence merely lowers confidence without invalidating dependent state;
- old history must be deleted to recover current validity;
- dependency cycle is silently ignored.

## Canonical rule

> Trazabilidad sin propagación de validez sólo explica de dónde vino una decisión; MOCATRIZ también debe saber cuándo esa decisión necesita dejar de tratarse como vigente.
