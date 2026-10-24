# SCN-037 · Partial Evidence Recovery

**Class:** MOCATRIZ trusted recovery / evidence integrity  
**Status:** PASS / CONTROLLED  
**Created:** 2026-10-24

## Problem

A structurally valid, correctly hashed Trusted Memory Snapshot can still be unsafe to
resume from when the evidence package is incomplete.

The dangerous failure mode is narrative completion: because the snapshot, manifest and
state are coherent, the system infers that missing evidence is non-material and resumes
as if the recovery were complete.

## Test

1. Start from a valid sealed snapshot and matching recovery manifest.
2. Omit the evidence inventory referenced by the manifest.
3. Require fail-closed rejection with `evidence_inventory_missing`.
4. Restore the evidence inventory but keep a necessary requirement missing.
5. Require `RECOVERABLE_WITH_EXCEPTIONS`; never promote to complete recovery.
6. Mark a critical requirement missing while keeping the snapshot itself valid.
7. Require `RECOVERY_BLOCKED` / reconstruction failure.

## PASS

- referenced evidence inventory cannot be silently omitted;
- necessary missing evidence degrades recovery explicitly;
- critical missing evidence blocks trusted reconstruction;
- snapshot coherence never substitutes for missing evidence.

## Canonical rule

> Un snapshot íntegro no convierte evidencia ausente en evidencia suficiente.

