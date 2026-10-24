# MOCATRIZ Test 12 · Source Authority Unavailable

**Scenario:** SCN-039  
**Error:** ERR-20261024-040  
**Status:** PASS  
**Validation date:** 2026-10-24

## Claim under test

A known required authority that cannot currently be retrieved is epistemically UNKNOWN,
not MISSING and not FAILURE.

## Defect found

The source adapter correctly emitted `available=false` and
`validation_status=UNKNOWN`, but manifest construction discarded unavailable evidence
before deriving status and therefore collapsed the requirement to `MISSING`.

## Control implemented

- no evidence record at all → `MISSING`;
- declared but wholly unavailable evidence → `UNKNOWN`;
- unavailable evidence IDs and source refs remain durable in the manifest;
- required-authority UNKNOWN remains fail-closed for canonicalization.

## Evidence

Control head:
`6e3d05ee7671e2aa4db5c3601a74cdbda214b301`

CI:
- Landscape Intelligence Schema #228 → SUCCESS
- SOA Intelligence A2 Persistence Static #100 → SUCCESS
- Terraform SOA Intelligence DEV Static #172 → SUCCESS
- SOA Intelligence Alpha Cognitive Loop #35 → SUCCESS
- SOA Intelligence Worker OCI Runtime Smoke #126 → SUCCESS

OCI #284 remains a separate security workstream.

## Result

PASS. ERR-20261024-040 is CONTROLLED.

## Canonical consequence

> No observable no significa inexistente: indisponibilidad de autoridad es UNKNOWN, ausencia demostrada de evidencia es MISSING.
