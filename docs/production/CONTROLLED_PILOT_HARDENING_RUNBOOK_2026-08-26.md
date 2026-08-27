# Controlled pilot production hardening runbook

Issue #19 remains a production gate. Repository controls may be prepared in advance, but the final receipt is `PASS` only after the provider evidence below is collected from the authorized Azure subscription.

## 1. Secrets and credentials

1. Create or select the controlled-pilot Key Vault with RBAC authorization, soft delete and purge protection.
2. Store the OIDC client secret, Web↔Core HMAC secret, PostgreSQL credential and current package-pull credential as separate secrets.
3. Grant each workload identity access only to the secrets it consumes.
4. Bind Container Apps secrets by Key Vault reference; do not copy values into GitHub variables, committed tfvars, receipts or logs.
5. Rotate and revoke every temporary P0/GHCR credential after the new references are healthy.
6. Record only secret names, versions and rotation timestamps as evidence—never values.

Required evidence flags: `managed_secret_store_bound`, `credentials_rotated`, `approved_idp_bound`.

## 2. Remote state and change control

1. Provision a dedicated state storage account/container outside this workload stack, with Blob versioning, soft delete, public access disabled and Entra ID authorization.
2. Copy `backend.production.hcl.example` to an operator-restricted untracked file and replace its non-secret identifiers.
3. Migrate deliberately with `terraform init -migrate-state -backend-config=<protected file>` and verify the local P0 state is no longer authoritative.
4. Generate a saved plan and JSON representation. Run the production gate with `--plan-json`; any delete/replace action keeps the gate blocked.
5. Apply only the exact reviewed plan after the protected GitHub environment approval. Never combine plan generation and unattended apply.

Required evidence flags: `remote_backend_initialized`, `plan_no_destroy_verified`.

## 3. Network and data access

PostgreSQL remains private and Core ingress remains internal. Blob already denies anonymous objects and shared-key authorization. Before production, add and verify the Blob private endpoint/private DNS path from the workload VNet, then disable its public network endpoint. Confirm the browser can reach only Web and cannot reach Core, PostgreSQL or Blob directly.

Required evidence flag: `blob_private_path_verified`.

## 4. Observability and cost

Log Analytics, application health routes and platform probes are configured. Before GO, create and trigger-test alerts for Web/Core unavailability, Worker failures and critical Azure service health. Create a resource-group budget alert sized to the approved pilot envelope. Verify Run → Job → Receipt correlation using `X-Correlation-ID` without recording tokens or secrets.

Required evidence flags: `alerts_verified`, `budget_alert_verified`.

## 5. Backup, restore and rollback

PostgreSQL provider backups and Blob versioning/soft-delete are configured for seven days. Before GO:

1. Restore PostgreSQL to an isolated temporary server and verify migrations, pgvector and a non-sensitive synthetic run/receipt.
2. Restore a deleted synthetic evidence object/version and verify its hash.
3. Roll back Core/Web/Worker by setting the three previous approved OCI digests, reviewing the no-destroy plan and applying that exact plan.
4. Re-run only health and one synthetic MOCK smoke flow after rollback.
5. Delete the isolated restore target after evidence is captured according to retention policy.

Required evidence flags: `postgres_restore_verified`, `evidence_backup_verified`, `rollback_verified`.

## Gate command

```powershell
python validation/prod_hardening_gate.py `
  --evidence .\infra\azure\p0\production-evidence.json `
  --plan-json .\infra\azure\p0\controlled-pilot.tfplan.json
```

The real evidence and plan files remain untracked. Exit code `0` means every mandatory family is `PASS`; exit code `2` means production remains blocked.
