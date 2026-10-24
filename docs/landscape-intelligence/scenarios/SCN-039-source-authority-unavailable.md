# SCN-039 · Source Authority Unavailable

**Class:** MOCATRIZ source authority / epistemic availability  
**Status:** ACTIVE / TESTABLE  
**Created:** 2026-10-24

## Problem

A required source can be known, correctly bound to an obligation, and temporarily
unavailable. That state is epistemically different from having no evidence record at all.

Collapsing an unavailable authority into `MISSING` destroys information about whether the
system lacks the source or merely cannot currently observe it.

## Test

1. Declare a required authority source.
2. Mark retrieval as unsuccessful (`retrieved=false`).
3. Require the adapter to emit `validation_status=UNKNOWN`.
4. Require the Recovery Manifest to preserve the requirement as `UNKNOWN`, not `MISSING`.
5. Preserve the unavailable evidence/source reference for diagnosis and retry.
6. Require canonicalization to remain blocked for required authority.
7. Remove the evidence record entirely and confirm the requirement becomes `MISSING`.

## PASS

- unavailable source remains UNKNOWN;
- absent evidence remains MISSING;
- required-authority UNKNOWN still blocks canonicalization;
- no unavailable source is interpreted as healthy or failed by inference.

## Canonical rule

> No observable no significa inexistente: indisponibilidad de autoridad es UNKNOWN, ausencia demostrada de evidencia es MISSING.
