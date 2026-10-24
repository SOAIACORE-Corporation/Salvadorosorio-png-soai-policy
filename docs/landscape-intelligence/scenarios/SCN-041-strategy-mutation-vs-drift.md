# SCN-041 · Strategy Mutation vs Drift

**Class:** MOCATRIZ adaptive execution / strategy integrity  
**Status:** ACTIVE / TESTABLE  
**Created:** 2026-10-24

## Problem

Counting a self-declared `strategy_mutation` does not prove adaptation. An agent can
rename arbitrary exploration as strategy change while drifting away from the objective
or cycling through previously failed routes without new evidence.

## Test

1. Keep one objective fixed.
2. Force three distinct strategies to fail with durable evidence.
3. Change strategy after each failure using the new evidence as basis.
4. Require those changes to classify as ADAPTIVE_MUTATION, not drift.
5. Revisit a previously failed strategy without new evidence.
6. Require DRIFT / UNPRODUCTIVE_REVISIT.
7. Change the objective while presenting the move as a strategy change.
8. Require DRIFT / OBJECTIVE_DEPARTURE.

## PASS

- strategy changes are derived from evidence, not caller labels;
- repeated failed routes without new evidence are drift;
- objective departure is drift;
- multiple failed strategies may still produce legitimate adaptation when evidence justifies the next move.

## Canonical rule

> Cambiar de estrategia es adaptación sólo cuando nueva evidencia modifica el camino sin abandonar el objetivo; explorar sin nueva información es deriva.
