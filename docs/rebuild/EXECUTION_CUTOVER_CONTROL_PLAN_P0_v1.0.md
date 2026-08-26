# SOAIACORE Rebuild P0 — Execution & Cutover Control Plan v1.0

Architecture: `SOAIACORE Architecture v0.6 FINAL / FROZEN FOR P0`

This is a **rebuild cutover**, not a production cutover. Historical runtime is destroyed/non-operational; production does not yet exist.

## Mandatory gate sequence

`SOA CONTEXT → SOA SYNC → SOA PRECHECK → EXECUTION → VALIDATION → RECEIPT → GO/NO-GO`

## Current checkpoint

- Phase: `P0-01 LOCAL PLATFORM BOOTSTRAP`
- Status: `WAITING_FOR_REBOOT`
- WSL2 + VirtualMachinePlatform: enabled
- RunOnce: prepared
- Immediate target: `SOAIACORE_LOCAL_POSTGRES_GATE=PASS`
- `AZURE_APPLY_EXECUTED=false`
- `CLOUD_RESOURCES_CREATED=0`

## Execution phases

1. **P0-01 Local Platform Bootstrap** — reboot, resume one-shot, Docker/Compose operational.
2. **P0-02 Local PostgreSQL + pgvector Gate** — migrations, synthetic seed, Identity/Evidence/Claim/ContextGraph/Receipt tests, negative constraints, teardown, receipt.
3. **P0-03 Repository Reconciliation / Build Baseline** — normalize AR v0.8 into the rebuild source tree; historical PR remains forensic/delta input only.
4. **P0-04 Minimum End-to-End Local Pipeline** — `CONTEXT → SYNC → PRECHECK → EXECUTION → AUTOMATED VALIDATION → REVIEW POLICY → RECEIPT`, using local web/core/worker semantics and MOCK/REPLAY.
5. **P0-05 Azure Terraform Design / Plan** — IaC, ZERO_FIRST, SKU/resource allowlist, TTL/teardown, `terraform validate/plan`; no apply.
6. **P0-06 Cloud GO/NO-GO** — explicit human approval required for Azure apply/spend.
7. **P0-07 Azure Pilot Ephemeral Integration** — authorized apply, synthetic integration tests, receipts; no permanent DEV/QA/STAGING/PROD matrix.
8. **P0-08 Benchmark / Resilience / Cost** — capacity envelope, connection limits, throughput, restart persistence, evidence lineage, selective-intelligence audit path, cost observation.
9. **P0-09 Teardown / Zero-Residual Check** — export evidence, `terraform destroy`, verify residual resources, DeploymentReceipt.
10. **P0-10 P0 Acceptance** — PASS / PASS_WITH_LIMITS / FAIL, demonstrated limits, deferred decisions, next release recommendation.

## Autonomy boundary

Control Tower may act without a new approval on documentation/registries, GitHub/Drive review, receipts, static validation, execution contracts, Codex one-shots, nomenclature, and implementation-compatible corrections on the rebuild branch.

Explicit human approval remains required for:
- Azure `terraform apply` or billable cloud resources;
- merge/release to `main`;
- Architecture v0.6 semantic changes;
- irreversible deletion of evidence/history;
- production promotion.

## Visibility format

Every checkpoint is reported as:

`PHASE | GATE | STATUS | EVIDENCE | BLOCKER | NEXT ACTION | CLOUD COST | OWNER`

After every Codex result, Control Tower must verify evidence, update Drive/registries, issue GO/NO-GO, and provide the next one-shot without reopening closed decisions absent new evidence.
