# SOAIACORE · Codex Execution Contract · Rebuild P0 · 2026-08-23

## Authority

- Architecture: `SOAIACORE Architecture v0.6 FINAL / FROZEN FOR P0`.
- Architecture v0.7 does not exist.
- Historical runtime: `DESTROYED / NON_OPERATIONAL`.
- Current state: `REBUILD P0`.
- Production: `NOT DEPLOYED`.
- Azure: P0 integration binding only; **NO Azure apply in this task**.
- FinOps: `ZERO_FIRST`.

## Repository

Repository: `SOAIACORE-Corporation/Salvadorosorio-png-soai-policy`

Working branch: `rebuild/p0-v0.6-final`

Historical PR #1 / branch `soaia/as-is-hardening-2026-08-17` is forensic/delta input only. Do not merge it as-is and do not treat it as current AS-IS or production.

## Authoritative implementation package

Drive artifact:

`SOAIACORE_AR_v0.8_Persistence_and_Azure_Readiness_FINAL.zip`

Drive file id: `1EmOJFGv-1slm9GYtXD4V849wANxOYpaw`

The package is an AR/readiness package, not Architecture v0.8.

If the package is not accessible to Codex, stop with:

`AR_PACKAGE_ACCESS=BLOCKED`

Do **not** reconstruct missing package files from memory or from the historical PR.

## Objective

Reach a verifiable:

`SOAIACORE_LOCAL_POSTGRES_GATE=PASS`

on the Windows development machine using PostgreSQL + pgvector locally, with no cloud deployment and no billable cloud dependency.

## Execution sequence

### 1. PRECHECK

Verify and record:

- Windows host and current user.
- Git installed and authenticated for the repository.
- repository clean or explicitly identify local changes;
- current branch is `rebuild/p0-v0.6-final`;
- Docker CLI available;
- `docker compose version` succeeds;
- Docker engine is running;
- no required secret is printed to console or committed.

Do not install or alter unrelated system software automatically. If Docker is unavailable, stop with a precise blocker instead of simulating a PASS.

### 2. Retrieve and verify AR v0.8

Obtain the authoritative ZIP from Drive.

Unpack into an isolated temporary workspace.

Read:

- `README.md`
- `validation/AR_v0.8_MANIFEST_FINAL.json`
- `validation/STATIC_AND_SEMANTIC_GATE.json`
- `validation/LOCAL_POSTGRES_GATE_PRECHECK.json`

Verify hashes/manifest where available.

### 3. Reconcile source tree

Do not overwrite historical PR content blindly.

Normalize the new rebuild implementation toward this target structure:

```text
contracts/
schemas/
db/
  migrations/
  tests/
docs/
  architecture/
  persistence/
  governance/
  azure/
deploy/
  local/
  azure/
validation/
receipts/
```

Rules:

1. Preserve PostgreSQL + pgvector as the P0 persistence baseline.
2. Preserve the three-deployable P0 architecture; do not create microservices per logical plane.
3. Preserve ContextGraph as a logical interface implemented on PostgreSQL for P0.
4. Preserve M0/M1/M2/M3 for maturity and E0–E5 for epistemics.
5. Preserve `MOCK / REPLAY / LIVE` execution modes.
6. Preserve conditional human review: `NONE / OPTIONAL / REQUIRED`.
7. Do not introduce Neo4j, Kafka, Kubernetes, dedicated vector DB, GPU runtime or other deferred components.
8. Historical `data/schema.sql` is delta/reference input only; it is not allowed to override the new canonical persistence model.

When path normalization changes scripts, update their relative paths and re-test them.

### 4. Static validation

Run the supplied static/semantic validation. It must PASS before PostgreSQL execution.

Any fix must remain implementation-level. If a fix would change canonical architecture semantics, STOP and report `ARCHITECTURE_DELTA_REQUIRED` rather than modifying v0.6 silently.

### 5. Local PostgreSQL + pgvector gate

Use the supplied local Docker/PowerShell gate or an equivalent faithful execution of the same migrations/tests.

Required behavior:

1. Create a fresh disposable PostgreSQL + pgvector instance.
2. Apply all migrations in order.
3. Verify `vector` extension.
4. Verify canonical schemas/tables.
5. Load synthetic/minimal seed only.
6. Test Identity persistence and decisions.
7. Test Evidence → EvidenceReference → Claim provenance chain.
8. Test ContextGraph edge persistence/traversal.
9. Test ContextReceipt persistence.
10. Confirm invalid probability without methodology/calibration is rejected.
11. Confirm invalid evidence FK is rejected.
12. Run architecture invariant and integrity tests.
13. Tear down the disposable DB and volume.

Do not use production or personal datasets.

### 6. Receipt

Create:

- `receipts/LOCAL_POSTGRES_GATE_2026-08-23.json`
- `receipts/LOCAL_POSTGRES_GATE_2026-08-23.md`

Receipt must include:

- architecture version;
- branch and commit SHA;
- host identifier without sensitive credentials;
- Docker/PostgreSQL/pgvector versions;
- migrations applied;
- tests executed;
- PASS/FAIL per test group;
- start/end timestamps;
- failures/fixes performed;
- confirmation `CLOUD_RESOURCES_CREATED=0`;
- confirmation `AZURE_APPLY_EXECUTED=false`;
- final status.

Only a real successful run may emit:

`SOAIACORE_LOCAL_POSTGRES_GATE=PASS`

### 7. Git discipline

If PASS:

- commit only to `rebuild/p0-v0.6-final`;
- use a clear rebuild/P0 commit message;
- do not merge to `main`;
- do not close or merge historical PR #1;
- leave the branch ready for review.

If FAIL:

- preserve logs/receipt;
- commit only safe diagnostic/fix changes if appropriate;
- report exact blocker;
- do not proceed to Azure.

## Stop conditions

Stop immediately on:

- architecture semantic conflict;
- missing authoritative AR package;
- inability to run PostgreSQL/pgvector for real;
- credential/identity mismatch;
- unexpected destructive operation;
- cloud resource creation requirement;
- requirement to merge historical PR as-is.

## Success condition

This task is complete only when the repository contains a verifiable local execution receipt and the real Windows run reports:

`SOAIACORE_LOCAL_POSTGRES_GATE=PASS`

After this gate, the next separate work item is Azure P0 Terraform **design/plan and ZERO_FIRST validation**, not an automatic cloud apply.
