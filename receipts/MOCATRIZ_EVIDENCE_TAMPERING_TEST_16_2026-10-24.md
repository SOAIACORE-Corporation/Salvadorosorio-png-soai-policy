# MOCATRIZ Test 16 · Evidence Tampering / Hash Mismatch

**Scenario:** SCN-043  
**Error:** ERR-20261024-043  
**Status:** PASS  
**Validation date:** 2026-10-24

## Claim under test

Trusted recovery must reject independently tampered snapshot, manifest or fidelity
receipt content. A different but internally valid receipt cannot substitute for the one
bound by the manifest.

## Defect found

Legacy fidelity receipts recorded hashes of surrounding artifacts but had no self-hash,
and legacy manifests referenced receipt paths without an expected receipt content hash.

## Control implemented

For the forward sealed-receipt contract:

- receipt carries a canonical self-hash;
- manifest binds receipt ID + expected receipt hash;
- receipt self-hash excludes only `manifest_hash` to avoid a circular hash dependency;
- `manifest_hash` is validated separately against the sealed manifest;
- snapshot and evidence-inventory hashes are cross-validated;
- a manifest-bound receipt is mandatory during trusted reconstruction.

Legacy manifests remain readable and are not silently upgraded to a guarantee they never had.

## Evidence

Control head:
`02c5d26e024b822c8f49c795561198bf3ddf057a`

CI:
- Landscape Intelligence Schema #250 → SUCCESS
- SOA Intelligence A2 Persistence Static #122 → SUCCESS
- Terraform SOA Intelligence DEV Static #194 → SUCCESS
- SOA Intelligence Alpha Cognitive Loop #57 → SUCCESS
- SOA Intelligence Worker OCI Runtime Smoke #148 → SUCCESS

OCI remains a separate security workstream.

## Result

PASS. ERR-20261024-043 is CONTROLLED.

## Canonical consequence

> La integridad de la evidencia certificadora debe ser verificable por contenido, no sólo por el nombre del archivo o por los hashes que el propio receipt declara.
