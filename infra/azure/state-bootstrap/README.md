# Azure Terraform Remote-State Bootstrap

**State:** SPECIFIED · NOT YET CLOUD-APPLIED

This directory codifies the dedicated Azure Blob state store required by the controlled-pilot hardening gate. It is deliberately outside `infra/azure/p0/` so the workload stack cannot accidentally destroy its own authoritative state store.

## Purpose

Create only the control-plane resources required by the `azurerm` backend:

- dedicated resource group;
- StorageV2 account with TLS 1.2 minimum;
- anonymous Blob access disabled;
- shared-key authorization disabled;
- Microsoft Entra authentication as the default;
- Blob versioning enabled;
- Blob/container soft delete enabled;
- private `tfstate` container;
- optional `Storage Blob Data Contributor` assignments for explicitly supplied Entra principals.

This bootstrap does **not** change the SOAiaCore workload, GHCR bindings, Container Apps, PostgreSQL, or application image digests.

## Required operator inputs

Supply these outside Git:

- authorized Azure `subscription_id`;
- a globally unique lowercase `storage_account_name`;
- the Entra object IDs that require state read/write access;
- any approved tag overrides.

Do not commit a real `.tfvars`, state, plan, or backend configuration file.

## Bootstrap sequence

From this directory, using Terraform 1.15.x and an authenticated Azure operator:

```powershell
terraform fmt -check
terraform init -backend=false
terraform validate
terraform plan -out=state-bootstrap.tfplan -var-file=state-bootstrap.tfvars
terraform show -json state-bootstrap.tfplan > state-bootstrap.tfplan.json
```

Review the exact plan before apply. A bootstrap plan is expected to create only the dedicated state resource group, storage account, private container, and explicitly requested RBAC assignments. Any delete/replace action is a STOP condition.

After human adjudication of the saved plan:

```powershell
terraform apply state-bootstrap.tfplan
```

The bootstrap's own local state is an operator-restricted control-plane artifact. Keep it outside Git and protect it according to the same state-handling policy; do not treat it as application state.

## Bind the controlled pilot

After the state store exists, create an operator-restricted copy of `../p0/backend.production.hcl.example` and replace only the non-secret identifiers with the verified bootstrap outputs:

```hcl
resource_group_name  = "<verified output>"
storage_account_name = "<verified output>"
container_name       = "tfstate"
key                  = "soaiacore/controlled-pilot/terraform.tfstate"
use_azuread_auth     = true
```

Then migrate deliberately from the authorized P0 state location:

```powershell
terraform init -migrate-state -backend-config=<protected-backend-file>
```

Do not claim `remote_backend_initialized = true` until the migrated backend can be read using Entra authorization and the subsequent saved workload plan is reviewed without delete/replace actions.

## Required receipt

Record only non-secret evidence:

- subscription scope identifier as permitted by policy;
- resource group / storage account / container names;
- RBAC principal object IDs or approved redacted identifiers;
- versioning and retention state;
- anonymous/shared-key access state;
- `terraform init -migrate-state` result;
- post-migration plan add/change/destroy counts;
- `remote_backend_initialized` and `plan_no_destroy_verified` gate states.

Never include access tokens, storage keys, state contents, secret values, or raw connection strings in receipts.