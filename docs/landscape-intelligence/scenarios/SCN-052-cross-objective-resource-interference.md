# SCN-052 · Cross-Objective Resource Interference

**Class:** MOCATRIZ multi-objective orchestration / execution isolation  
**Status:** PASS / CONTROLLED  
**Created:** 2026-10-24

## Problem

MOCATRIZ treats the objective as the unit of execution. Two objectives can each be valid
in isolation while becoming unsafe when executed concurrently against the same resource.

A numeric priority or execution order is not, by itself, authority to discard one objective
or let incompatible mutations race.

## Test

1. Present two objectives with WRITE actions against the same resource and different
   desired-state hashes.
2. Give one objective a higher declared numeric priority.
3. Require ARBITRATION_REQUIRED and no automatic winner.
4. Present two WRITE actions against the same resource and the same desired-state hash.
5. Require COALESCE_REQUIRED rather than double execution.
6. Present READ + WRITE against the same material resource.
7. Require SERIALIZE_REQUIRED.
8. Present READ + READ on one shared resource plus writes to disjoint resources.
9. Require CLEAR / parallel execution allowed.
10. Mark one conflicting action non-material.
11. Require it not to create a false conflict.

## PASS

- incompatible writes cannot execute concurrently;
- declared priority alone does not invent authority;
- identical writes are coalesced rather than duplicated;
- read/write interference is serialized;
- independent work remains parallelizable;
- non-material actions do not create artificial blocking.

## Nullifiers

- two incompatible writes are both allowed;
- numeric priority silently selects a winner without governance;
- identical writes execute twice;
- all concurrency is blocked indiscriminately;
- disjoint objectives are serialized without need.

## Canonical rule

> Dos objetivos pueden ser correctos por separado y peligrosos juntos; autonomía multiobjetivo exige detectar interferencia antes de ejecutar.
