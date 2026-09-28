# Landscape Intelligence · F2 Canonical Model Validation Receipt

**Date:** 2026-09-26  
**Branch:** `feat/landscape-intelligence-data-model-v1`  
**PR:** #84  
**Status:** VALIDATED / DRAFT / NO PRODUCTION EFFECT

## Scope validated

- Canonical JSON Schema v0.1
- Source provenance and authority semantics
- Azure resource adapter
- Azure Cost adapter
- Terraform plan adapter
- Terraform State adapter
- GitHub IaC adapter
- Monitoring adapter
- Deterministic bundle builder
- Canonical identity helpers
- Read-only multi-source reconciler
- Manifest-driven local collector
- P0 five-source baseline fixture

## Acceptance evidence

GitHub Actions workflow:

`Landscape Intelligence Schema · run #24`

Result:

```text
32 passed in 2.10s
```

## Behavioral controls validated

- UNKNOWN is not converted to zero.
- A difference is not converted automatically to FIX.
- A single source cannot manufacture a contradiction.
- Terraform and GitHub matching intent produces no drift finding.
- Terraform and GitHub mismatch produces PENDING / OPEN / UNKNOWN severity.
- Decision records require explicit authority.
- Derived cost requires a formula where applicable.
- Bundle hash is deterministic regardless of input order.
- Collector rejects path traversal outside its manifest base directory.
- Unsupported execution-oriented source kinds are rejected.
- Canonical asset identity is stable and independent of display name.

## P0 multi-source test

The repository baseline fixture normalizes five source classes:

1. Azure physical resource
2. Terraform State
3. GitHub IaC
4. Azure Cost
5. Monitoring

Expected result:

- 5 canonical records
- deterministic bundle SHA-256
- 0 false drift findings for aligned Terraform/GitHub state

## Execution boundary

This validation performed:

- no Azure mutation
- no Terraform apply
- no RBAC change
- no production deployment
- no database write
- no external material action

The collector and reconciler remain read-only.

## Adjudication

F2 has crossed from design-only to executable normalized-data capability.

This receipt does **not** authorize merge, deployment, cloud mutation, or autonomous remediation.

Next controlled step:

**expand source extraction fidelity and begin F3 correlation rules over canonical bundles while PR #84 remains reviewable.**
