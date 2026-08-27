# SECURITY P0 PRECHECK — 2026-08-27

## Scope
Baseline freeze for the SOAiaCore P0 Security Change Package prior to any code, IAM, Terraform, secret-plane, or Azure deployment change.

## Repository baseline
- Repository: `SOAIACORE-Corporation/Salvadorosorio-png-soai-policy`
- Base branch: `main`
- Base commit: `09b2d1455d170c0c1a2b75275f7f9641242003b7`
- Working branch: `security/p0-hardening-2026-08-27`
- Main protected: `true`
- Required status checks observed: `CodeQL`, `Analyze (javascript-typescript)`, `Analyze (actions)`, `Analyze (python)`

## AS-IS security controls
- Web runtime: Next.js `16.3.2`; React `19.2.8`; ReactDOM `19.2.8`.
- `next.config.mjs`: standalone output, poweredByHeader disabled, React strict mode; image optimization is not disabled yet.
- OCI workflow: `.github/workflows/oci-build-publish.yml`.
- Workflow trigger: push to `rebuild/p0-06a-runtime` plus manual dispatch.
- GitHub Actions: pinned by immutable commit SHA.
- Trivy: scanners `vuln,secret`; severity gate `CRITICAL`; `.trivyignore.yaml` present.
- Identity model: User Assigned Managed Identities `workload` and `deployer`.
- Federated identity resource: `azurerm_federated_identity_credential`.
- Current OIDC subject model: repository branch trust through `${var.github_branch}`.
- Current default trusted branch variable: `rebuild/p0-v0.6-final`.
- Deployer RBAC: `Contributor` plus `Role Based Access Control Administrator` on pilot Resource Group.
- Container Apps secret model: PostgreSQL password supplied from Terraform-managed random password; GHCR token supplied through Terraform variable.
- Web ingress external; Core ingress private; Worker implemented as Container App Job.
- Remote backend: `backend.production.hcl.example` exists but provider-backed migration is not evidenced as complete.
- Issue #19 baseline: `BLOCKED`; `PRODUCTION_GO=NO`.

## Frozen implementation invariants
- `SEC-EXC-01`: preserve UAMI + `azurerm_federated_identity_credential`; no migration to App Registration federation.
- `SEC-EXC-02`: preserve immutable SHA pinning for GitHub Actions; no `@master`, `@main`, or mutable tags.
- `SEC-EXC-03`: RBAC removal must occur through Terraform desired state; Azure CLI reserved for read-only audit/verification except documented break-glass.
- `GOV-CUST-01`: critical approvals, OCI digests, Terraform state operations, secret rotations, deployment evidence, and rollback evidence require verifiable receipts.
- `DOC-SYNC-01`: architecture, runbooks, security docs, and receipts must match the deployed state before closure.

## EXEC-00 gate
- `ASIS_BASELINE=PASS`
- `MAIN_PROTECTED=PASS`
- `BASE_COMMIT_FROZEN=PASS`
- `SEC_EXC_01_RECORDED=PASS`
- `SEC_EXC_02_RECORDED=PASS`
- `SEC_EXC_03_RECORDED=PASS`
- `GOV_CUST_01_RECORDED=PASS`
- `DOC_SYNC_01_RECORDED=PASS`
- `AZURE_RESOURCES_CHANGED=NO`
- `TERRAFORM_APPLIED=NO`
- `PRODUCTION_GO=NO`

## Next authorized execution
`EXEC-01 — Web Security Patch`: update Next.js `16.3.2 -> 16.3.3`, preserve React/ReactDOM, add `images.unoptimized=true`, update lockfile, and require web tests/build before proceeding.
