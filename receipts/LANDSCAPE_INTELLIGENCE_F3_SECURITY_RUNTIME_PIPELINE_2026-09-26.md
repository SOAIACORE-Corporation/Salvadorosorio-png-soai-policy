# Landscape Intelligence · F3 Security Runtime Decision Pipeline Receipt

**Date:** 2026-09-26  
**Branch:** `feat/landscape-intelligence-data-model-v1`  
**PR:** #84  
**Status:** VALIDATED / READ-ONLY / COMMITTEE DECISION SUPPORT

## Capability validated

End-to-end read-only analysis now supports:

SOURCE → NORMALIZE → BUNDLE → CORRELATE → DERIVE DEPENDENCIES → DECISION CASE

Coverage includes:

- Azure physical resources
- Cost
- Terraform plan
- Terraform State
- GitHub IaC
- Monitoring
- Security / RBAC
- Application runtime
- GitHub pull requests
- COMITE / Drive decisions

## New policies

- Runtime dependencies are derived as canonical dependency records.
- Runtime health degradation creates a PENDING risk case.
- Broad Key Vault Secrets User scope can create a PENDING security case.
- Secret-scoped RBAC does not create a broad-access finding.
- Decision Cases remain non-ranked and do not generate Decision Records.
- Execution authority remains separate.

## Acceptance evidence

GitHub Actions:

`Landscape Intelligence Schema · run #39`

Result:

```text
48 passed in 3.63s
```

## Execution boundary

No Azure mutation.  
No Terraform apply.  
No RBAC mutation.  
No database write.  
No production deployment.  
No autonomous remediation.

## Adjudication

F2 normalization is functionally complete for the ten mapped source classes.

F3 correlation and committee decision support are now active implementation surfaces.

Next controlled step:

**expand live extraction fidelity and persist historical canonical bundles/decision cases without changing operational authority.**
