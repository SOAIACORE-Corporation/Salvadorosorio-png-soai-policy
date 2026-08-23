# SOAIACORE Azure P0 Integration Binding v0.1

**Architecture:** v0.6 FINAL / FROZEN FOR P0

**Status:** SPECIFICATION ONLY — NO RESOURCES CREATED

## Mapping

| SOAIACORE capability | Azure P0 mapping |
|---|---|
| `soaiacore-web` | Azure Container Apps |
| `soaiacore-core` | Azure Container Apps |
| `soaiacore-worker` | Container Apps Jobs |
| PostgreSQL + pgvector | Azure Database for PostgreSQL where selected/validated |
| Canonical evidence | Blob Storage |
| AI workspace | Blob/Data Lake-compatible workspace semantics |
| Events | Event Grid + Service Bus only when required |
| Secrets | Key Vault when required |
| Container images | Azure Container Registry |
| GitHub federation | Entra / GitHub OIDC |
| Models | Foundry/model adapters; MOCK/REPLAY/LIVE |
| Tools | Azure/native/MCP adapters |
| Observability | MINIMAL by default; BENCHMARK temporarily |

## P0 operating policy

- `COST_MODE = ZERO_FIRST`
- no permanent DEV/QA/STAGING/PROD cloud environment matrix;
- routine development remains local;
- provider pilot is bounded/ephemeral;
- every ephemeral resource group must have owner, purpose, expiry and executable teardown;
- LIVE model calls require explicit purpose/provider/cost gate;
- benchmark evidence, receipts and cost summary are exported before teardown;
- Azure binding does not alter canonical table/schema semantics.

## Deployment gate

This document is not deployment authorization.

Terraform implementation follows after:
1. local migrations validate;
2. canonical integrity tests pass;
3. schema/contract validation passes;
4. Azure SKU/resource allowlist is reviewed;
5. cost/TTL teardown controls are implemented.
