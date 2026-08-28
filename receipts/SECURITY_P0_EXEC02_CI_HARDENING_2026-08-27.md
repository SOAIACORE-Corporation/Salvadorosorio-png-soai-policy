# SECURITY P0 · EXEC-02 CI / Supply Chain Hardening · 2026-08-27

- `EXECUTION`: `EXEC-02`
- `STATUS`: **IN_PROGRESS**
- `BRANCH`: `security/p0-hardening-2026-08-27`
- `BASE_MAIN`: `09b2d1455d170c0c1a2b75275f7f9641242003b7`
- `AZURE_RESOURCES_CHANGED`: **NO**
- `TERRAFORM_APPLIED`: **NO**
- `PRODUCTION_GO`: **NO**

## Implemented changes pending PR validation

- Global workflow permissions reduced to `contents: read`.
- `build-test-scan` has no `packages: write` and no `id-token: write`.
- `publish` is a separate job with `packages: write`, gated to `push` on `main` only.
- PR execution cannot publish OCI images.
- Actions remain pinned to immutable commit SHAs (`SEC-EXC-02`).
- Added pinned `actions/download-artifact` commit `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c` to transfer the exact scanned OCI bundle into the publish job.
- Trivy deployment gate raised to `HIGH,CRITICAL` with `ignore-unfixed: true` and existing governed `.trivyignore.yaml`.
- Separate HIGH/CRITICAL vulnerability inventory is emitted without `ignore-unfixed`, so unfixed risk remains visible even when the deployment gate passes.
- The exact locally built and scanned Core/Web/Worker images are saved as one Docker bundle for later publication; the publish job does not rebuild them.
- `.trivyignore.yaml` statements now document owner, technical basis, compensating control, and expiration behavior using supported fields only.

## Gate status

- `WORKFLOW_PERMISSION_SEGREGATION`: **PENDING_PR_RUN**
- `PR_PACKAGES_WRITE`: **EXPECTED_NONE**
- `PR_ID_TOKEN_WRITE`: **EXPECTED_NONE**
- `ACTION_SHA_PINNING`: **PASS_STATIC**
- `TRIVY_HIGH_CRITICAL_FIXABLE_GATE`: **PENDING_PR_RUN**
- `TRIVY_UNFIXED_RISK_INVENTORY`: **PENDING_PR_RUN**
- `TESTS_CORE_WORKER`: **PENDING_PR_RUN**
- `TESTS_WEB`: **PENDING_PR_RUN**
- `WEB_BUILD`: **PENDING_PR_RUN**
- `OCI_BUILD_CORE_WEB_WORKER`: **PENDING_PR_RUN**
- `OCI_PUBLISH_ON_PR`: **MUST_NOT_RUN**
- `EXEC02_FINAL`: **PENDING**

## Invariants

- `SEC-EXC-01`: unaffected; no Azure identity resource changed.
- `SEC-EXC-02`: enforced; all GitHub Actions are referenced by immutable SHA.
- `SEC-EXC-03`: unaffected; no RBAC modification performed.
- `GOV-CUST-01`: this receipt records the controlled execution.
- `DOC-SYNC-01`: canonical documentation synchronization remains required before final package closure.
