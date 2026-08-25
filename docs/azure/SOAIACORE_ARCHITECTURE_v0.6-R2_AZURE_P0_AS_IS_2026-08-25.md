# SOAIACORE Architecture v0.6-R2 — Azure P0 AS-IS

- **Status:** AS-IS evidence revision for the live internal P0 pilot
- **Snapshot:** 2026-08-25
- **Canonical architecture:** v0.6 FINAL / FROZEN FOR P0
- **Semantic architecture delta:** NONE
- **Environment:** INTERNAL_ENGINEERING_PILOT
- **Production:** NOT DEPLOYED

## Purpose and authority

R2 records the effective Azure implementation observed after P0-07 and the
initial P0-08 baseline. It reconciles the earlier design-only binding with the
real deployed topology. It does not create Architecture v0.7, promote P0 to
production, authorize LIVE providers, or change canonical persistence and
lifecycle semantics.

Primary evidence:

- `receipts/P0_AZURE_APPLY_E2E_OBSERVATION_2026-08-25.json`
- `docs/azure/AZURE_P0_PRIVATE_GHCR_BINDING_DECISION_2026-08-24.md`
- `docs/rebuild/ADR_P0_LOCAL_TERRAFORM_STATE_EXCEPTION_2026-08-24.md`
- `infra/azure/p0/`

## Effective Azure topology

```text
Internet
   |
   | HTTPS
   v
Web — Azure Container App, external ingress, 0..1 replicas
   |
   | HTTPS to stable internal ingress FQDN
   v
Core — Azure Container App, internal ingress, 0..1 replicas
   |                         |
   | private PostgreSQL      | managed identity
   v                         v
Azure PostgreSQL 17       Blob Storage / evidence
+ pgvector

Worker — Azure Container Apps Job, manual trigger
   | private PostgreSQL + managed identity to evidence storage
   +-- finite MOCK lifecycle execution

All workloads -> Log Analytics
All workload images <- private GHCR by immutable digest
```

The pilot is contained in one TTL-tagged resource group in `eastus2` and one
Container Apps environment using the Consumption workload profile. The network
is `10.42.0.0/23` with:

- `10.42.0.0/27` delegated to `Microsoft.App/environments`;
- `10.42.1.0/28` delegated to PostgreSQL Flexible Server;
- a private PostgreSQL DNS zone linked to the VNet.

## Deployed components

| Component | Effective P0 implementation |
|---|---|
| Web | Azure Container App, external HTTPS ingress on port 3000, 0.25 vCPU, 0.5 GiB, min 0/max 1 |
| Core | Azure Container App, internal HTTPS ingress on port 8000, 0.25 vCPU, 0.5 GiB, min 0/max 1 |
| Worker | Manual Azure Container Apps Job, 0.25 vCPU, 0.5 GiB, one completion, retry limit 1, timeout 1800 s |
| Canonical memory | Azure Database for PostgreSQL Flexible Server 17, `Standard_B1ms`, 32 GiB, private network, HA disabled, seven-day backup |
| Vector capability | `azure.extensions` permits `vector`; migrations created and health validated pgvector |
| Canonical evidence bytes | Standard LRS Blob Storage, private container, workload identity receives Blob Data Contributor |
| Identity | Separate workload and deployer user-assigned managed identities; GitHub branch OIDC credential on deployer identity |
| Observability | Log Analytics, 30-day retention, Container Apps system and console logs |
| Lifecycle | TTL/expiry `2026-09-01T04:00:00Z`; Terraform teardown is mandatory |

Event Grid, Service Bus, Key Vault, ACR, Foundry/LIVE providers, Kubernetes,
Kafka, GPU runtime, graph database, and a dedicated vector database are not
deployed in P0.

## Private GHCR bindings

GHCR visibility remains `PRIVATE`. Core, Web, and Worker each have one registry
binding to `ghcr.io` and reference a local Container Apps secret. The temporary
PAT classic is limited to `read:packages`, supplied to Terraform only as a
sensitive value outside Git, and must be revoked at teardown.

The effective immutable image references are:

- Core: `ghcr.io/soaiacore-corporation/soaiacore-core@sha256:e6564cad60afa7f7e1828c193c3512c7f1b0ce53aed26459e0a61b8ac33fb467`
- Web: `ghcr.io/soaiacore-corporation/soaiacore-web@sha256:da26fd8bcf6cb2a4c242d380a28c682b19c6f094f0a898258a727ef558fa6c58`
- Worker: `ghcr.io/soaiacore-corporation/soaiacore-worker@sha256:971dc02fd1ba2306cd6e1d4864e8d7de0d447169256f7d89071bc5c94ccde9a1`

Azure system logs confirmed successful private pulls for the exact digests. No
package was made public, no `:latest` reference exists, and no ACR was created.

## Effective application bindings

### Web to Core

Web uses the stable internal Core ingress FQDN:

`https://ca-soaiacore-p0-core-34utxi.internal.purplebay-18375c47.eastus2.azurecontainerapps.io`

It does not bind to a revision-specific `--<revision>` hostname. This preserves
the Web-to-Core path when Core receives an in-place revision.

### Python runtime

Core and Worker set:

`PYTHONPATH=/app/.venv/lib/python3.12/site-packages`

This is a non-secret Azure runtime binding required by the already-approved
images. It does not rebuild or change either OCI digest.

### Provider mode

Core, Web, and Worker remain in `MOCK`. No LIVE provider call was made during
P0-07 or the recorded P0-08 baseline.

## P0-08 empirical baseline

At the snapshot:

- Web live, Web ready, and Core ready returned HTTP 200;
- Core reported PostgreSQL `PASS`, eight migrations, pgvector `PASS`, and MOCK;
- Worker precheck passed with eight migrations and MOCK;
- one and only one cloud E2E MOCK execution completed with exit code 0;
- the run persisted one claim, seven lifecycle stages in `PASS`, and a receipt;
- persistence survived Core scale-to-zero and reactivation;
- three warm ready observations measured 741 ms, 384 ms, and 400 ms;
- Container Apps system logs reported zero image-pull failures in the observed
  30-minute window;
- Terraform final drift validation reported `No changes`.

The first cost query returned no usage records because Azure cost ingestion was
still pending. This is not evidence of zero cost. The approved planning envelope
remains USD 3.82–20.28 for 168 hours; P0-08 must append observed cost once Azure
publishes it.

## Logs and observability

Log Analytics is the empirical source for:

- private image pull success/failure;
- revision/container start and termination events;
- migration and Worker precheck pass events;
- the single `RUN_ONE_RESULT` event;
- cold-start, scale-to-zero, and reactivation evidence.

Secrets, state values, passwords, connection strings, PATs, and raw environment
variable values are excluded from architecture evidence and receipts.

## P0 versus production deltas

| Concern | P0 AS-IS | Required before production |
|---|---|---|
| Terraform state | Authorized operator-restricted local exception | Dedicated protected remote backend, locking, access control, backup and recovery |
| Registry credential | Temporary human-owned read-only PAT | Governed non-human credential or approved managed registry pattern with rotation and audit |
| Compute | Consumption, min 0/max 1, no availability target | Capacity test, autoscaling policy, availability/SLO design and regional decision |
| PostgreSQL | B1ms, 32 GiB, HA disabled, seven-day backup | Production sizing, HA/zone decision, restore test, retention and DR objectives |
| Network edge | Direct public Web ingress; Core and DB internal | Approved edge/WAF/custom-domain/TLS, egress and private-access controls |
| Secrets | Container Apps secrets; sensitive values also exist in Terraform state | Governed secret store, rotation, least privilege and incident procedure |
| Observability | 30-day Log Analytics baseline; no alert program | Production dashboards, alerts, SLOs, retention, audit export and on-call ownership |
| Cost | Short-lived TTL pilot; ingestion initially pending | Budget, alerts, allocation tags, forecast and continuous FinOps controls |
| Providers | MOCK only | Explicit provider authorization, data governance, quotas and cost gates before any LIVE use |
| Lifecycle | Mandatory teardown at pilot expiry | Production change, release, rollback, backup and decommission lifecycle |

None of these production deltas is silently authorized by R2.

## Required closure

P0-08 continues through the observation window without another E2E or mass load.
At expiry, P0-09 must:

1. retain only evidence explicitly approved for retention;
2. run `terraform destroy` using the protected local P0 state;
3. verify the resource group and pilot resources are absent;
4. revoke the temporary GHCR PAT;
5. securely remove the DPAPI credential, Terraform state, backup state, and
   sensitive plan files;
6. emit a sanitized teardown/zero-residual receipt.
