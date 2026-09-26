# Landscape Intelligence · Durable Source Adapters · 2026-09-26

## Objective

Remove the next manual boundary by converting heterogeneous durable artifacts into the normalized evidence inventory consumed by the Recovery Manifest generator.

## Implemented

- `tools/landscape/durable_evidence_adapters.py`
- Git commit adapter
- CI run adapter
- Receipt adapter
- Snapshot adapter
- Decision adapter
- explicit requirement binding
- deterministic freshness calculation
- preservation of source outcome separately from evidence validity
- `run_memory_cycle_from_sources()`
- end-to-end source → evidence → manifest → memory cycle test
- SCN-027 sidecar scenario

## Core semantic result

A failed source outcome is not automatically low-quality evidence.

Example:
- CI status: completed
- CI outcome: failure
- evidence validity: CONFIRMED

This allows SOAiaCore to preserve negative results without corrupting provenance semantics.

## Execution learning

A second combined GitHub write was rejected after the first connector policy block had already been marked controlled.

That recurrence is recorded as:
- `ERR-20260926-019`
- class: `REGRESSION`

The execution then switched to bounded one-file writes without operator intervention.

## Acceptance

Pending final CI validation on the source-adapter E2E test and error-register update.
