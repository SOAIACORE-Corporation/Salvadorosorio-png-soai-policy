# Landscape Intelligence · Context Integrity & Recovery Confidence v0.1 Receipt

**Date:** 2026-09-26  
**Branch:** `feat/landscape-intelligence-data-model-v1`  
**PR:** #84  
**Status:** VALIDATED / DETERMINISTIC / READ-ONLY

## Capability

SOAiaCore can now quantify evidentiary context continuity with a reproducible 0–100 score.

Canonical dimensions:
- evidence coverage = 30%
- causal continuity = 25%
- authority integrity = 20%
- source freshness = 15%
- receipt integrity = 10%

Every dimension is derived from explicit `confirmed / expected` counts.

## Claim gates

A high arithmetic score cannot hide critical provenance failures:
- missing required authority caps claimable confidence at 84%
- missing material primary evidence caps claimable confidence at 69%
- unrecovered verbatim dialogue is disclosed separately and does not by itself invalidate independently recovered state

The score is explicitly **not** a probability that an AI answer is true.

## Scenario coverage

Added:
- SCN-021 Context / History Gap
- SCN-022 State exists, rationale missing

Required behavior includes:
- detect discontinuity
- recover durable evidence
- distinguish facts, decisions, inferred sequence and unrecovered gaps
- never manufacture missing dialogue or rationale
- publish measurable Context Integrity

## Validation

GitHub Actions workflow: Landscape Intelligence Schema  
Run: #92  
Run ID: 36224037476  
Result: **114 passed in 5.18s**  
Conclusion: SUCCESS

An earlier run (#89) failed because the new test used an import style inconsistent with the existing repository test layout. The defect was corrected and revalidated; the failed run is retained as part of the audit trail.

## Safety boundary

No Azure mutation.  
No Terraform apply.  
No RBAC mutation.  
No PostgreSQL write.  
No production deployment.  
No autonomous remediation.  
No merge.

## Next control

Build an evidence inventory/recovery manifest so Context Integrity can be calculated directly from recovered artifacts rather than manually supplied counts, then bind the score to committee-ready Context Recovery Cases and historical snapshots.
