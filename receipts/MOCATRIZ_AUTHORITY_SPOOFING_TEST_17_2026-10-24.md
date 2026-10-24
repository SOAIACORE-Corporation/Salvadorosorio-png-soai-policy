# MOCATRIZ Test 17 · Authority Spoofing

**Scenario:** SCN-044  
**Error:** ERR-20261024-044  
**Status:** PASS  
**Validation date:** 2026-10-24

## Claim under test

A declared canonical name or alias is not sufficient evidence of operational authority.

## Defect found

The exception gate accepted `authority="SOA"` plus a reason and returned
`AUTHORIZED_EXCEPTION` without requiring durable authentication provenance.

## Control implemented

Operational exception authorization now requires all three:

1. canonical authority identity or accepted alias;
2. `authority_ref = authority:soa:salvador-osorio-ayala`;
3. non-empty upstream `authentication_ref`.

The module validates canonical binding and provenance presence; it does not replace the
upstream identity provider or claim cryptographic authentication itself.

The canonical Exception Authority Policy was updated to state:

`DECLARED IDENTITY != AUTHENTICATION != OPERATIONAL AUTHORITY`

## Evidence

Code control:
`6aef41658d160c7728e891bf3fddba2b0f64a592`

Canonical policy alignment:
`fe0c3d92608d6068c299a34b29ed8c7ff8d04770`

CI on aligned head:
- Landscape Intelligence Schema #258 → SUCCESS
- SOA Intelligence A2 Persistence Static #130 → SUCCESS
- Terraform SOA Intelligence DEV Static #202 → SUCCESS
- SOA Intelligence Alpha Cognitive Loop #65 → SUCCESS
- SOA Intelligence Worker OCI Runtime Smoke #156 → SUCCESS

OCI remains a separate security workstream.

## Result

PASS. ERR-20261024-044 is CONTROLLED.

## Canonical consequence

> Conocer el nombre de la autoridad no concede autoridad; una excepción exige identidad canónica más evidencia durable de autenticación.
