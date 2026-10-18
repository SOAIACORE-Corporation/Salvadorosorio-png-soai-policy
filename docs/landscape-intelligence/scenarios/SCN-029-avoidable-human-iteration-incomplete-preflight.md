# SCN-029 · Avoidable Human Iteration / Incomplete Preflight

**Status:** ACTIVE / TESTABLE  
**Historical aliases:** precursor-thread proposal `SCN-023`; provisional consolidation label `SCN-027`.  
**Canonical ID:** `SCN-029`.

## Purpose

Verify that SOAiaCore exhausts machine-verifiable, read-only prerequisites before requesting a material human action.

## Setup

Five prerequisites are available:

1. `DEPENDENCIES`
2. `PERMISSIONS`
3. `COLLISIONS`
4. `COMPATIBILITY`
5. `EXISTING_STATE`

All five are machine-verifiable and required before the first human action.

## Defective path

The system validates only the first three, requests a human action, then discovers `COMPATIBILITY` and requires rework; `EXISTING_STATE` is discovered afterward.

Expected:

- `FAIL_PRECHECK_MISS`
- explicit `missed_precondition_ids`
- avoidable human interaction > 0
- Human Interaction Efficiency < 100%
- no security or authority relaxation to improve the metric

## Corrected path

The system validates all five read-only prerequisites before requesting the one genuinely authority-bound action.

Expected:

- `PASS`
- `missed_precondition_ids=[]`
- `avoidable_human_actions=0`
- Avoidable Human Interaction Rate = 0%
- Human Interaction Efficiency = 100% when one necessary human action exists

## Zero-denominator rule

When no human action occurs, the metric state is `NOT_EXERCISED`, not a fabricated 100%.

## Implementation

- `tools/landscape/human_interaction.py`
- `schemas/tests/test_human_interaction_efficiency.py`

## Governance

The objective is zero avoidable human actions, not zero human authority. Proactivity never grants execution authority.
