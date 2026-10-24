# Landscape Intelligence · Evidence-Driven Recovery Manifest v0.1 Receipt

**Date:** 2026-09-26  
**Branch:** `feat/landscape-intelligence-data-model-v1`  
**PR:** #84  
**Status:** VALIDATED / EVIDENCE-DRIVEN / READ-ONLY

## Capability

Context Integrity can now be derived from a declared evidence inventory rather than manually supplied scoring counts.

Each required item declares:
- requirement_id
- dimension
- required
- status = CONFIRMED / MISSING / STALE / PARTIAL / UNKNOWN
- optional material_primary
- optional required_authority

The engine derives:
- confirmed vs expected counts per dimension
- unconfirmed requirement IDs
- missing material primary-evidence gate
- missing required-authority gate
- claimable Context Integrity score and confidence band

This prevents the scoring layer from choosing convenient numerators after the fact.

## Validation

GitHub Actions workflow: Landscape Intelligence Schema  
Run: #94  
Run ID: 36224107907  
Result: **117 passed in 3.91s**  
Conclusion: SUCCESS

## Safety boundary

No Azure mutation.
No Terraform apply.
No RBAC mutation.
No PostgreSQL write.
No production deployment.
No autonomous remediation.
No merge.

## Next control

Generate recovery manifests automatically from append-only snapshots, receipts, GitHub/CI, COMITE and live read-only sources, then persist the resulting Context Integrity assessment beside each trusted snapshot.
