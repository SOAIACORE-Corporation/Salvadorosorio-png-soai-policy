# Landscape Intelligence · Durable Evidence Manifest Automation · 2026-09-26

## Objective

Automate the remaining manual boundary in the memory pilot: generate the Recovery Manifest from durable evidence and feed it directly into the Memory Integrity Cycle.

## Implemented

- `tools/landscape/recovery_manifest_builder.py`
- `run_memory_cycle_from_evidence()`
- deterministic evidence-to-status rules
- provenance via evidence IDs and source references
- tests for missing, stale, partial and undeclared evidence
- SCN-026
- durable-evidence pilot fixture

## Critical control

Requirement policy remains separate from observed evidence.

This prevents a falsely high continuity score produced by redefining requirements after seeing what evidence happens to be available.

## Expected behavior

- Missing → MISSING
- Stale → STALE
- Partial → PARTIAL
- Unknown → UNKNOWN
- Sufficient current evidence → CONFIRMED
- Missing required authority/material primary evidence → existing fail-closed gates

## Authority

READ-ONLY. No merge, Azure/Terraform mutation, production deployment or autonomous source rewrite.

## Acceptance

Pending integrated CI validation.
