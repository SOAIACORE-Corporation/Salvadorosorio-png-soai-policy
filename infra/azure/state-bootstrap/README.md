# Azure Terraform Remote-State Bootstrap / Adoption

**State:** SPECIFIED + STATIC_VALIDATED · EXISTING AZURE RESOURCES DISCOVERED · AUTHORITY NOT YET VERIFIED

This directory codifies the dedicated Azure Blob state store required by the controlled-pilot hardening gate. It lives outside `infra/azure/p0/` so the workload stack cannot accidentally destroy its own authoritative state store.

## Current discovery

Read-only Azure discovery on 2026-09-02 found an existing dedicated state resource group and storage account:

- resource group: `rg-soaiacore-tfstate-34utxi`
- storage account: `stsoaiacoretf34utxi`
- region: `eastus2`

Observed management-plane controls include HTTPS-only transport, TLS 1.2 minimum, anonymous Blob access disabled, shared-key access disabled, and deny-by-default storage network rules.

The container name, actual state blob/key, effective versioning/soft-delete settings, and authoritative-state status remain evidence-gated. A Cloud Shell data-plane listing returned 403 because that session used an ephemeral MSI identity rather than the user identity holding Blob Data Contributor.

**Do not create a second state store while the discovered resources may already be authoritative.**

## Create-new versus adopt-existing

### Adopt existing — current default path

When the resource group/storage account already exist:

1. verify exact resource identifiers through Azure management plane;
2. verify container name and recovery controls;
3. verify a durable Entra data-plane identity/path;
4. import the existing Azure resources into the bootstrap Terraform state before planning changes;
5. run a saved plan and require **zero delete/replace actions**;
6. reconcile only missing hardening controls (for example a missing `CanNotDelete` lock) through a reviewed plan;
7. determine whether workload state is already authoritative before running any `-migrate-state` operation.

Example import pattern — use only verified identifiers and keep the bootstrap state outside Git:

```powershell
terraform init -backend=false
terraform import -var-file=state-bootstrap.tfvars azurerm_resource_group.state "/subscriptions/<subscription-id>/resourceGroups/<verified-resource-group>"
terraform import -var-file=state-bootstrap.tfvars azurerm_storage_account.state "/subscriptions/<subscription-id>/resourceGroups/<verified-resource-group>/providers/Microsoft.Storage/storageAccounts/<verified-storage-account>"
terraform import -var-file=state-bootstrap.tfvars azurerm_storage_container.state "https://<verified-storage-account>.blob.core.windows.net/<verified-container>"
```

Import IDs must be verified against the AzureRM provider version in use before execution. If the provider requires a different container import identifier, STOP and use the provider-documented form rather than guessing.

### Create new — exception path only

Creating a new state store is allowed only when read-only evidence establishes that no authoritative existing backend should be adopted. A create plan must contain only the intended dedicated resource group, StorageV2 account, private container, deletion lock, and explicitly requested RBAC assignments. Any unexpected duplicate, delete, or replace action is a STOP condition.

## Required operator inputs

Supply outside Git:

- authorized Azure `subscription_id`;
- exact verified `resource_group_name`;
- exact verified `storage_account_name`;
- exact verified `container_name`;
- Entra object IDs that require state read/write access;
- an approved private path or the minimum temporary operator IPv4/CIDR ranges through `allowed_ip_ranges` when no private operator path is available;
- approved tag overrides.

The resource-group and container variables intentionally have **no generic defaults**. This prevents accidental creation of parallel state infrastructure from convenient placeholder names.

Do not commit real `.tfvars`, Terraform state, saved plans, JSON plans, backend configuration, tokens, keys, or raw connection strings.

## Desired hardening

The module declares:

- StorageV2 with TLS 1.2 minimum;
- anonymous Blob access disabled;
- shared-key authorization disabled;
- Microsoft Entra authentication as default;
- deny-by-default storage network rules;
- Blob versioning enabled;
- Blob/container soft delete;
- private state container;
- `CanNotDelete` management lock;
- Terraform `prevent_destroy` guards;
- optional `Storage Blob Data Contributor` assignments for explicitly supplied Entra principals.

The module does **not** change SOAiaCore workload resources, GHCR bindings, Container Apps, PostgreSQL, or application image digests.

## Validation / plan sequence

Using Terraform 1.15.x and an authenticated Azure operator:

```powershell
terraform fmt -check
terraform init -backend=false
terraform validate
terraform plan -out=state-bootstrap.tfplan -var-file=state-bootstrap.tfvars
terraform show -json state-bootstrap.tfplan > state-bootstrap.tfplan.json
```

Review the exact saved plan. Delete/replace actions or unplanned duplicate resources are STOP conditions. Apply only the exact reviewed saved plan after human adjudication.

## Bind the controlled pilot

After authoritative backend resources and the container are verified, create an operator-restricted copy of `../p0/backend.production.hcl.example`:

```hcl
resource_group_name  = "<verified resource_group_name>"
storage_account_name = "<verified storage_account_name>"
container_name       = "<verified container_name>"
key                  = "<verified authoritative state key>"
use_azuread_auth     = true
```

Run `terraform init -migrate-state` **only if evidence proves migration is necessary**. If the state blob is already authoritative, bind to it without manufacturing a migration event.

Do not claim `remote_backend_initialized = true` until the backend can be read with Entra authorization through the approved network path and a subsequent saved workload plan is reviewed without delete/replace actions.

## Naming rule

Do not rename the state container for aesthetics while authority is unresolved. Azure container renaming is effectively a create/copy/delete migration and introduces unnecessary state risk. Cosmetic naming can be reconsidered only after authority, backup/recovery, and rollback are proven.

## Required receipt

Record only non-secret evidence:

- subscription scope identifier as permitted by policy;
- resource group / storage account / container names;
- approved/redacted RBAC principal identifiers;
- deny-by-default network state and approved access path;
- versioning and retention state;
- anonymous/shared-key access state;
- deletion lock / destroy-guard state;
- adoption/import or migration result;
- post-binding workload plan add/change/destroy counts;
- `remote_backend_initialized` and `plan_no_destroy_verified` states.

Never include state contents, access tokens, storage keys, secret values, or raw connection strings in receipts.
