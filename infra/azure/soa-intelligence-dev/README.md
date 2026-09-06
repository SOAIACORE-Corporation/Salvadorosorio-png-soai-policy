# SOA Intelligence · A2 PostgreSQL DEV

## Purpose

Isolated Azure Database for PostgreSQL Flexible Server for **SOA Intelligence A2 · Real Persistence + Cognitive Adapters**.

This stack is intentionally independent from Azure P0 application state and must never reuse the P0 Terraform state key or PostgreSQL database.

## Architecture

- Resource group: `rg-soa-intelligence-dev`
- Region: `eastus2`
- PostgreSQL: Flexible Server 17
- Compute: `B_Standard_B1ms` (development / Burstable)
- Storage: 32 GiB / P4
- Database: `soa_intelligence`
- Extension allowlist: `vector`
- Backup retention: 7 days
- Geo-redundant backup: disabled
- HA: disabled for DEV
- Public network access: disabled
- Network: dedicated VNet + delegated PostgreSQL subnet + private DNS zone
- Terraform destroy guard: `prevent_destroy = true`

## Governance boundary

This stack follows SOA Intelligence R0-R3 policy.

- `terraform fmt`, `init -backend=false`, `validate`: R0/R1 validation only.
- `terraform plan` against live Azure/state: R1/R2 depending on credentials and state reads; must emit evidence.
- `terraform apply`: R2 material change. Requires an explicit approved gate.
- Any delete, `prevent_destroy` removal, resource-group deletion, IAM broadening, database purge, or state surgery: R3 and requires explicit individual human authorization.

## Remote state

The stack declares an empty `azurerm` backend and requires a governed backend configuration at initialization.

Use a **dedicated key**:

```text
soa-intelligence/dev/postgres.tfstate
```

Do not reuse any P0 key.

Example:

```bash
cp backend.hcl.example backend.hcl
# populate the governed backend identifiers
terraform init -backend-config=backend.hcl
```

`backend.hcl` must not be committed.

## Required variable

```bash
export TF_VAR_subscription_id='<subscription-id>'
```

No database password is accepted from source control. Terraform generates the bootstrap administrator password using the `random` provider. The password therefore exists only as sensitive Terraform state and Azure control-plane configuration. A2 application credentials/Entra authentication are a separate follow-on gate.

## Static validation

The PR workflow performs only:

1. `terraform fmt -check`
2. a backend-free copy of the stack
3. `terraform init -backend=false`
4. `terraform validate`

It performs **no Azure login, no plan, no apply, no destroy**.

## Apply preconditions

Before the first live apply:

1. Remote backend identity is freshly reconciled and reachable.
2. Dedicated state key is configured.
3. Azure identity/subscription scope is verified.
4. Resource group name does not collide with existing resources.
5. Cost posture is accepted for DEV.
6. R2 authorization is explicit and current.
7. A post-apply probe path exists from a workload inside the VNet; the database has no public endpoint.

## A2 definition of success

Infrastructure alone is not PASS. A2 persistence is PASS only when all of the following are evidenced:

- Flexible Server provisioned.
- Private DNS resolves from the runtime network.
- TLS PostgreSQL connection succeeds.
- migration/schema creation succeeds.
- bitemporal write/read test succeeds.
- `vector` extension can be created in the target database.
- project isolation tests remain PASS.
- receipt captures server ID, database name, migration version, test run, and no-secret evidence.

## Explicit non-goals

- Reusing the P0 PostgreSQL server.
- Production HA.
- Public PostgreSQL access.
- Storing secrets in GitHub or documentation.
- Granting the LLM direct database credentials.
