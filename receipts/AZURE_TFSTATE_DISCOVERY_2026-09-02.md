# Azure Terraform State Discovery Receipt · 2026-09-02

**Classification:** SANITIZED OPERATIONAL EVIDENCE  
**Authority:** read-only Azure discovery performed from authenticated Cloud Shell  
**Related trackers:** #38, #19, #40  
**Decision state:** authorized to continue validation; no cloud mutation asserted by this receipt

## Scope

This receipt records only non-secret facts observed during read-only discovery of the Azure controlled-pilot Terraform-state infrastructure. It intentionally omits account identifiers, tenant/subscription identifiers, access tokens, keys, state contents, connection strings, and full RBAC object IDs.

## Resource discovery

Observed in Azure `eastus2`:

- dedicated Terraform-state resource group: `rg-soaiacore-tfstate-34utxi`;
- Terraform-state Storage Account: `stsoaiacoretf34utxi`;
- workload resource group also present: `rg-soaiacore-p0-34utxi`;
- the workload inventory includes Container Apps Core/Web, Worker Container Apps Job, PostgreSQL Flexible Server, Key Vault, managed identities, private endpoints/private DNS, workload storage, Log Analytics and operational alert resources.

## State Storage Account management-plane observations

| Control | Observed | State |
|---|---|---|
| Storage kind | StorageV2 | PASS |
| Region | eastus2 | PASS |
| HTTPS only | enabled | PASS |
| Minimum TLS | TLS 1.2 | PASS |
| Anonymous Blob public access | disabled | PASS |
| Shared-key access | disabled | PASS |
| Public network endpoint | enabled with storage firewall | CONDITIONAL |
| Firewall default action | Deny | PASS |
| Firewall bypass | AzureServices | REVIEW |
| Explicit IP rule(s) | present | REVIEW |
| Resource access rule(s) | present | REVIEW |
| Management lock | none returned by read-only query | OPEN |

`PublicNetworkAccess=Enabled` is not treated as unrestricted public exposure because the observed network rule set uses `DefaultAction=Deny`; effective path validation remains required.

## RBAC observation

Read-only scope inspection showed the authorized human operator has control-plane ownership/access-administration rights and a Blob data-plane contributor assignment on the state Storage Account. Multiple Microsoft Defender service principals also have expected scanner/operator assignments.

Full principal identifiers are deliberately omitted from this public receipt.

## Data-plane observation

Attempting to list Blob containers from Cloud Shell with `New-AzStorageContext -UseConnectedAccount` returned:

`403 AuthorizationFailure`

The Cloud Shell context identified itself through an ephemeral managed identity rather than the human user identity holding the Blob data-plane role. Therefore:

- the 403 is **not evidence that no container/state exists**;
- the 403 is **not a secret finding**;
- no permission was granted to the ephemeral Cloud Shell MSI as a workaround;
- a durable approved Entra identity/path is still required to verify the container and state blob.

## Evidence still required

The following remain OPEN:

1. exact existing container name;
2. exact authoritative Terraform state blob/key;
3. Blob versioning effective state;
4. Blob/container soft-delete effective retention;
5. deletion protection / `CanNotDelete` lock;
6. durable data-plane read path using approved Entra authorization;
7. whether the existing backend is already authoritative or needs state migration;
8. subsequent saved Terraform workload plan with no delete/replace actions.

## Safety decisions

- Do **not** create a second Terraform-state Storage Account while the discovered account may already be authoritative.
- Do **not** rename the existing container for aesthetics until state authority, recovery and rollback are verified.
- Do **not** claim `remote_backend_initialized=true` or `plan_no_destroy_verified=true` from this receipt alone.
- Any missing hardening control must be reconciled through a reviewed Terraform plan or equivalent governed change path; no ad-hoc cloud mutation is evidenced here.

## Receipt verdict

`AZURE_STATE_RESOURCE_DISCOVERY = PASS`  
`MANAGEMENT_PLANE_BASELINE = PARTIAL_PASS`  
`DATA_PLANE_STATE_AUTHORITY = EVIDENCE_PENDING`  
`DELETION_PROTECTION = OPEN`  
`REMOTE_BACKEND_INITIALIZED = NOT_YET_PROVEN`  
`PLAN_NO_DESTROY_VERIFIED = NOT_YET_PROVEN`
