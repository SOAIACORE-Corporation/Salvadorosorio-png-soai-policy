# SCN-040 · False Completion on Zero Applicable Criteria

**Class:** MOCATRIZ closure integrity / false completion  
**Status:** ACTIVE / TESTABLE  
**Created:** 2026-10-24

## Problem

MOCATRIZ already rejects COMPLETED when a material applicable criterion remains open.
A separate false-completion path exists when the denominator is zero: no applicable
acceptance criteria can currently produce 100% completion and therefore COMPLETED.

That is not evidence of completion. It is absence of an exercised completion basis.

## Test

1. Evaluate an objective with zero applicable criteria.
2. Require `objective_completion_pct=null`, never 100.
3. Require `completion_applicable=false`.
4. Require `determine_final_status` to return PENDING, not COMPLETED.
5. Claim COMPLETED manually and require `detect_false_completion` to flag it.
6. Reconfirm that one unresolved material criterion also rejects completion.

## PASS

- zero denominator never becomes 100%;
- no acceptance basis cannot produce COMPLETED;
- explicit false completion is detected;
- existing material-gap protections remain intact.

## Canonical rule

> Ausencia de criterios aplicables no demuestra terminación; 0/0 es NOT_EXERCISED, no 100%.
