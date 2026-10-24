# MOCATRIZ Test 14 · Strategy Mutation vs Drift

**Scenario:** SCN-041  
**Error:** ERR-20261024-042  
**Status:** PASS  
**Validation date:** 2026-10-24

## Claim under test

Multiple failed strategies can still represent legitimate adaptation when every strategy
change is supported by new evidence and preserves the same objective. Repeating a failed
route without new evidence, or silently changing the objective, is drift.

## Control implemented

`assess_strategy_adaptation(...)` derives classification from:

- objective continuity;
- actual prior FAILED/PARTIAL result;
- basis evidence tied to that result;
- actual strategy change;
- novelty of revisiting a previously attempted route.

It does not trust a caller-supplied `strategy_mutation` label.

## Evidence

Control head:
`5d413f80847329c36a7cba50670bcf8e144a1208`

CI:
- Landscape Intelligence Schema #240 → SUCCESS
- SOA Intelligence A2 Persistence Static #112 → SUCCESS
- Terraform SOA Intelligence DEV Static #184 → SUCCESS
- SOA Intelligence Alpha Cognitive Loop #47 → SUCCESS
- SOA Intelligence Worker OCI Runtime Smoke #138 → SUCCESS

OCI #296 remains a separate security workstream.

## Result

PASS. ERR-20261024-042 is CONTROLLED.

## Canonical consequence

> Cambiar de estrategia es adaptación sólo cuando nueva evidencia modifica el camino sin abandonar el objetivo; explorar sin nueva información es deriva.
