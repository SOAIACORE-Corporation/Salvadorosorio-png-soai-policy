# SECURITY P0 — EXEC-04 OIDC / Identity Trust Boundary Precheck

Date: 2026-08-27
Repository: `SOAIACORE-Corporation/Salvadorosorio-png-soai-policy`
Branch: `security/p0-identity-2026-08-27`

## Purpose

Prepare the GitHub Actions → Microsoft Entra OIDC trust migration without contacting Azure, without running Terraform, and without changing deployed resources.

## Invariants

- `SEC-EXC-01`: User Assigned Managed Identity (UAMI) and `azurerm_federated_identity_credential` model preserved.
- `SEC-EXC-02`: GitHub Actions remain pinned to immutable commit SHAs.
- `SEC-EXC-03`: no RBAC mutation is performed outside Terraform desired state.
- `GOV-CUST-01`: OIDC evidence is recorded without logging the raw JWT.
- `DOC-SYNC-01`: final production documentation remains a required later gate.

## Empirical GitHub OIDC observation

Authoritative workflow run: `33133801817`
Authoritative artifact: `oidc-sub-precheck-254e72f3eb7338670661c1692428bfcb751eb6d5`
Artifact digest: `sha256:e21ae1528573789ce71b5ea508035277e7c9d78e4fe2e5e3bd148287ab30116f`

Observed safe claims:

- issuer: `https://token.actions.githubusercontent.com`
- audience: `api://AzureADTokenExchange`
- subject mode: `LEGACY_DEFAULT`
- subject: `repo:SOAIACORE-Corporation/Salvadorosorio-png-soai-policy:ref:refs/heads/security/p0-identity-2026-08-27`
- repository: `SOAIACORE-Corporation/Salvadorosorio-png-soai-policy`
- repository ID: `1062316959`
- repository owner ID: `244666106`
- environment claim: absent for the branch-only precheck, as expected
- Azure calls: `0`
- raw JWT logged: `NO`

## Derived target subject

Because the repository empirically emits the GitHub default legacy subject template and GitHub documents that an environment-bound job replaces the branch/ref context with `environment:<name>`, the target FIC subject is prepared as:

`repo:SOAIACORE-Corporation/Salvadorosorio-png-soai-policy:environment:production`

The exact case of `SOAIACORE-Corporation` is preserved from the observed token. A lowercase substitute is not authorized.

This derived value is NOT yet accepted as the final live trust receipt. A production-environment OIDC token must still be observed after GitHub Environment `production` is independently confirmed to exist with required protection rules.

## Prepared source changes

- `infra/azure/p0/identity.tf`
  - branch-scoped FIC desired state replaced with environment-scoped FIC desired state.
  - UAMI architecture preserved.
  - RBAC resources intentionally unchanged in EXEC-04; RBAC reduction belongs to EXEC-05.
- `infra/azure/p0/variables.tf`
  - `github_branch` replaced by fixed `github_environment = "production"`.
  - repository claim case pinned to the empirically observed value.
  - approved EXEC-03 Core/Web/Worker OCI digests synchronized into Terraform validation.

## Explicitly not executed

- Azure login: NO
- Azure CLI: NO
- Azure API/provider calls: NO
- Terraform init/validate/plan/apply: NO
- FIC created or changed in Microsoft Entra: NO
- Azure resources changed: NO
- RBAC changed: NO
- deployment to Azure: NO

## Gate status

- `OIDC_ISSUER_VERIFIED=PASS`
- `OIDC_AUDIENCE_VERIFIED=PASS`
- `OIDC_REPOSITORY_CLAIM_VERIFIED=PASS`
- `OIDC_SUBJECT_MODE_OBSERVED=PASS`
- `OIDC_RAW_TOKEN_LOGGED=NO`
- `OIDC_TARGET_SUBJECT_PREPARED=PASS`
- `OCI_DIGESTS_SYNCED_TO_IAC=PASS`
- `GITHUB_ENVIRONMENT_PRODUCTION_PROTECTED=PENDING_EXTERNAL_VERIFICATION`
- `OIDC_ENVIRONMENT_SUB_OBSERVED=PENDING`
- `OIDC_ENVIRONMENT_TRUST_APPLIED=NO`
- `EXEC04_FINAL=BLOCKED_SAFE`
- `PRODUCTION_GO=NO`

## Next controlled transition

1. Independently verify that GitHub Environment `production` already exists and has required reviewers plus deployment branch restrictions.
2. Only after that verification, execute an environment-bound OIDC claim observation with no Azure login and no Terraform.
3. Compare the observed `sub` byte-for-byte with the prepared FIC subject.
4. If and only if they match, authorize Terraform planning for the environment FIC in the subsequent approved gate.
