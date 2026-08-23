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

Do **not** reconstruct missing package files from memory or from the historical PR.

## Objective

Reach a verifiable:

`SOAIACORE_LOCAL_POSTGRES_GATE=PASS`

on the Windows development machine using PostgreSQL + pgvector locally, with no cloud deployment and no billable cloud dependency.

## Execution mode — ONE-SHOT / IDEMPOTENT

The canonical Windows entrypoint is:

`deploy/local/SOAIACORE-RebuildP0-OneShot.ps1`

This replaces the previous manual multi-step remediation flow.

Required properties:

1. One user/Codex task starts the workflow.
2. Safe to rerun after failure, interruption or reboot.
3. Detects existing prerequisites and does not reinstall them unnecessarily.
4. Uses a durable checkpoint under `%ProgramData%\SOAIACORE\RebuildP0`.
5. Elevates only when local prerequisite changes require administrator rights.
6. May install/enable only prerequisites required for the local gate: WSL2/VirtualMachinePlatform and Docker Desktop/Compose.
7. Must not install unrelated software.
8. When a reboot is necessary, it registers a one-time resume command. `-AutoReboot` may be used only when the operator has explicitly authorized an automatic Windows restart.
9. Reconciles the AR package into the rebuild tree by copy-if-different semantics.
10. Executes the real PostgreSQL + pgvector gate, tears down the disposable runtime and writes receipts.
11. Never executes Azure apply and never creates cloud resources.

## Codex sequence

### A. Obtain authoritative AR package

Use the connected Drive access to retrieve Drive file ID `1EmOJFGv-1slm9GYtXD4V849wANxOYpaw` to a local temporary/download path. Verify the expected file name and non-zero size.

If Drive access itself fails, return exactly:

`AR_PACKAGE_ACCESS=BLOCKED`

Do not synthesize the package.

### B. Execute the one-shot

From branch `rebuild/p0-v0.6-final`, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\deploy\local\SOAIACORE-RebuildP0-OneShot.ps1" -RepoPath "$PWD" -ArZip "<LOCAL_VERIFIED_AR_ZIP_PATH>"
```

If the operator explicitly authorizes unattended restart, add `-AutoReboot`.

The local AR path is an execution argument, not a committed configuration value.

### C. Idempotent behavior

The one-shot must:

- verify repository + expected branch;
- preserve/stop on unrelated dirty worktree changes;
- enable WSL2/VirtualMachinePlatform only when missing;
- install Docker Desktop via the Windows package manager only when missing;
- start/wait for Docker engine only when needed;
- verify Docker Compose;
- expand AR v0.8 into an isolated workspace;
- reconcile contracts/schemas/migrations/tests/docs into canonical rebuild paths by hash/copy-if-different;
- execute the supplied real local PostgreSQL gate;
- validate PostgreSQL + pgvector, migrations, identity, evidence/claims, ContextGraph, receipts and negative constraints;
- tear down disposable containers/volumes unless explicitly preserving a failed runtime for debugging;
- write BLOCKED/PASS receipts;
- clear resume state after PASS.

## Architecture constraints

1. Preserve PostgreSQL + pgvector as the P0 persistence baseline.
2. Preserve the three-deployable P0 architecture; do not create microservices per logical plane.
3. Preserve ContextGraph as a logical interface implemented on PostgreSQL for P0.
4. Preserve M0/M1/M2/M3 for maturity and E0–E5 for epistemics.
5. Preserve `MOCK / REPLAY / LIVE` execution modes.
6. Preserve conditional human review: `NONE / OPTIONAL / REQUIRED`.
7. Do not introduce Neo4j, Kafka, Kubernetes, dedicated vector DB, GPU runtime or other deferred components.
8. Historical `data/schema.sql` is delta/reference input only; it is not allowed to override the new canonical persistence model.

Any fix must remain implementation-level. If a fix would change canonical architecture semantics, STOP and report:

`ARCHITECTURE_DELTA_REQUIRED`

## Receipt

Create/maintain:

- `receipts/LOCAL_POSTGRES_GATE_2026-08-23.json`
- `receipts/LOCAL_POSTGRES_GATE_2026-08-23.md`

Receipt must include architecture, branch/commit, safe host identifier, Docker/Compose and database versions when available, migrations/tests, timestamps, failures/fixes, retry/reboot counts and confirmations:

- `CLOUD_RESOURCES_CREATED=0`
- `AZURE_APPLY_EXECUTED=false`

Only a real successful run may emit:

`SOAIACORE_LOCAL_POSTGRES_GATE=PASS`

## Git discipline

If PASS:

- commit only to `rebuild/p0-v0.6-final`;
- include reconciled implementation files and receipts;
- do not merge to `main`;
- do not close or merge historical PR #1;
- leave branch ready for review.

If BLOCKED:

- preserve the blocker receipt/logs;
- commit only safe implementation/diagnostic changes if appropriate;
- rerun the same one-shot after remediation;
- do not proceed to Azure.

## Stop conditions

Stop on:

- architecture semantic conflict;
- Drive AR package inaccessible;
- missing Windows package-manager capability needed to install Docker (`WINGET_UNAVAILABLE`);
- virtualization/WSL failure that cannot be remediated safely;
- credential/identity mismatch;
- unrelated dirty repository state;
- unexpected destructive operation;
- cloud resource creation requirement;
- requirement to merge historical PR as-is.

## Success condition

This task is complete only when the real Windows run reports:

`SOAIACORE_LOCAL_POSTGRES_GATE=PASS`

After this gate, the next separate work item is Azure P0 Terraform **design/plan and ZERO_FIRST validation**, not an automatic cloud apply.
