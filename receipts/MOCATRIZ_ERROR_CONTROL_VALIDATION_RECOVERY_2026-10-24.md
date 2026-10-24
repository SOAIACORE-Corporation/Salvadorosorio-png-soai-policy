# MOCATRIZ Recovery Receipt · Error-Control Validation Contract

**Error:** ERR-20261024-035  
**Status:** CONTROLLED  
**Date:** 2026-10-24

## Failure

Landscape #205 failed with `unsupported validation status: None`.

## Cause

New VAL-ERR records used conceptual fields `effective_status` and `validated_at`
instead of the canonical loader contract `status` and `observed_at`.

## Recovery

The governed validation artifacts were aligned to the existing VAL-* contract without
changing the underlying MOCATRIZ authority controls.

## Proof

Landscape Intelligence Schema #206 → SUCCESS.

## Learning

Before adding a member to a governed artifact family, inspect both a canonical sibling
and the consuming loader/schema. Semantic correctness does not excuse contract mismatch.
