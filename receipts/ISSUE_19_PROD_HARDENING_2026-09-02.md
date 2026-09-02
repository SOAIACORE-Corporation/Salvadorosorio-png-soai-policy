# Issue #19 · Controlled Pilot Production Hardening Reconciliation · 2026-09-02

**Status:** BLOCKED / MATERIAL PROGRESS  
**Scope:** evidence reconciliation after live Azure read-only discovery and Git hardening updates  
**Production authorization:** NO

## Delta since 2026-08-26 receipt

The 2026-08-26 receipt remains historical evidence. This receipt records only newly observed or reconciled facts and does not overwrite prior provenance.

### Functional / identity / governance

- #15 functional E2E gate: CLOSED.
- #18 minimum OIDC/session/RBAC gate: CLOSED.
- #16 Git governance implementation gate: CLOSED; canonical governance policy and PR checklist are now adopted in the repository.
- Effective GitHub `main` enforcement still requires administrative re-verification because repository rulesets currently return none and classic branch-protection read is unavailable to the connected integration.
- PR #35 is retained as DRAFT/BLOCKED pending explicit protected GitHub Environment `production` under #39.

### Terraform state / change control

Observed in live Azure:

- dedicated state RG `rg-soaiacore-tfstate-34utxi`;
- Storage Account `stsoaiacoretf34utxi` in `eastus2`;
- HTTPS only: enabled;
- minimum TLS: 1.2;
- anonymous Blob access: disabled;
- shared-key access: disabled;
- network rules: default deny, AzureServices bypass, explicit access rules present;
- management lock: none returned by read-only query.

Data-plane container/state listing returned 403 from Cloud Shell because the session used an ephemeral MSI rather than the human Blob-contributor identity. State absence is therefore **not** established.

The bootstrap module has since been hardened to require explicit discovered RG/container identifiers and to use an adopt-existing-first workflow. Generic create-first defaults were removed. See #38 and closed #40.

**Verdict:** CONDITIONAL / authority + recovery + deletion protection still open.

### Network / data access

Observed live Azure resources include:

- private endpoints for Blob and Key Vault;
- private DNS zones/links;
- PostgreSQL Flexible Server;
- Container Apps environment with Core/Web and Worker Job;
- workload storage and Log Analytics.

Current Terraform declares:

- PostgreSQL public network access disabled;
- Core ingress internal only;
- evidence container private;
- shared access keys disabled for evidence storage;
- workload managed identity with Blob Data Contributor;
- Web remains the public BFF surface.

**Verdict:** PARTIAL_PASS / effective runtime path testing still required.

### Secrets / credentials

Live Azure contains Key Vault `kv-soaiacore-p0-34utxi`, but current `main` Terraform does not declare/adopt it or use Key Vault-backed secret references.

Current Terraform still places:

- PostgreSQL password into Container Apps secrets from `random_password.postgresql.result`;
- GHCR pull credential into Container Apps secrets from `var.ghcr_token`.

These values are not committed to Git, but direct Terraform-managed secret values can be represented in Terraform state. Existing Key Vault adoption and secret-delivery reconciliation are tracked in #44.

**Verdict:** CONDITIONAL / secret-state exposure reduction + rotation evidence open.

### Observability

Current Terraform provides:

- Log Analytics workspace with 30-day retention;
- Container Apps logs routed to Log Analytics;
- Core/Web liveness and readiness probes.

Live Azure inventory additionally shows an action group, service-health alert, Core/Web unavailable metric alerts and Worker-failed alert.

Alert existence is **not equivalent to trigger-tested operational readiness**. End-to-end notification delivery and correlation through Run → Job → Receipt remain to be verified.

**Verdict:** CONDITIONAL.

### Backup / restore / rollback

Current Terraform declares:

- PostgreSQL native backup retention: 7 days;
- geo-redundant database backup: disabled;
- evidence Blob versioning + 7-day Blob/container soft delete;
- immutable/pinned OCI image digests and Container Apps `Single` revision mode.

An isolated PostgreSQL restore or provider-supported recovery proof has not yet been recorded. Application rollback exercise evidence is also still required. Tracked in #5.

**Verdict:** BLOCKED pending runtime restore/rollback evidence.

## Current control matrix

| Control family | Verdict | Primary open tracker |
|---|---|---|
| Functional E2E | PASS | — |
| Authentication / RBAC implementation | PASS | runtime PRA verification remains |
| Git governance policy | PASS | #39 effective enforcement/admin settings |
| Terraform backend authority | CONDITIONAL | #38 |
| Backend deletion/recovery controls | BLOCKED | #38 |
| Network/data design | PARTIAL_PASS | #19 / #20 |
| Secrets / credential delivery | CONDITIONAL | #44 |
| Observability | CONDITIONAL | #19 |
| Backup / restore / rollback | BLOCKED | #5 |
| Production Environment / OIDC release boundary | BLOCKED | #39 / PR #35 |
| Final PRA | NOT_RUN | #20 |

## Final verdict

`ISSUE_19_STATUS = BLOCKED_WITH_MATERIAL_PROGRESS`  
`PRODUCTION_GO = NO`  
`ARCHITECTURE_CHANGE_REQUIRED = NO`  
`NEXT_CRITICAL_PATH = #38 + #44 + #5 + #39 → #19 closure → #20 PRA`

No production apply/release is authorized by this receipt. Human adjudication remains required for the exact reviewed production-candidate plan and residual risks.
