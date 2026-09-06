# SOA Intelligence A2 · Persistence Overlay v0.1

**Workstream:** A2-PERSISTENCE-01  
**Issue:** #60  
**Status:** R1 implementation candidate / no live DB mutation  
**Base authority:** `main=c1d9c06ba35a7fbb9b8e15c78c69147073054e93`

## 1. Scope

This overlay advances the already-provisioned isolated A2 PostgreSQL substrate into the persistence semantics required by SOA Intelligence without changing the P0 runtime migration directory.

The P0 baseline remains in `db/migrations`. A2-specific persistence lives in `db/a2_migrations` and is invoked explicitly through `soaiacore_runtime.a2_persistence`.

## 2. Four active persistence cores

| Core | Physical relation |
|---|---|
| CanonicalMemory | `soa_memory.canonical_memory` |
| EpisodicTemporalMemory | `soa_memory.episodic_temporal_memory` |
| OperationalState | `soa_memory.operational_state` |
| Decision Ledger / DecisionOS | `soa_decision.decision_ledger` |

All four require `project_scope` and are append-only. A change in interpretation, canonical admission, operational state, or decision is represented by a new version/event rather than an in-place rewrite of history.

## 3. Temporal contract

Persisted records preserve:

- `event_time`
- `observed_time`
- `recorded_time`
- `valid_from`
- `valid_until`

As-of reads require both:

1. **valid-time cutoff** — what was valid at the situated moment;
2. **recorded-time cutoff** — what was already known/recorded by that moment.

The SQL functions enforce `recorded_time <= p_recorded_at`. This is the structural T2→T1 leakage guard: later evidence cannot appear in a query reconstructed at an earlier record-time.

## 4. Epistemic contract

Canonical memory admits the following persisted epistemic classes:

- `DOCUMENTED_FACT`
- `CONFIRMED_CONTEXT`
- `INFERENCE`
- `HYPOTHESIS`
- `WORKING_ASSUMPTION`
- `STALE_INFORMATION`

Persistence of an inference does not by itself make it canonical. `admission_state` remains distinct and as-of canonical reads return only rows explicitly marked `ADMITTED`.

This preserves the architecture rule:

> pensar ≠ afirmar como hecho ≠ persistir ≠ canonizar ≠ autorizar ≠ ejecutar

## 5. Source → Claim → Memory lineage

The existing baseline already models Evidence→Claim through `soa_core.claim_evidence`. The A2 overlay completes the chain with `soa_memory.memory_claim_lineage`:

`source artifact → evidence reference → claim → memory admission/version`

Lineage roles are explicit: `SOURCE`, `SUPPORT`, `CONTRADICTION`, `ADMISSION_BASIS`.

## 6. DecisionOS

Decision events preserve the frozen states:

`PROPOSED → APPROVED → EXECUTED → VALIDATED`

with terminal/evolution states:

`SUPERSEDED`, `REVOKED`, `FAILED`.

Each event carries an authority level `R1/R2/R3`. Database constraints require a `human_authorization_ref` for every R3 event.

## 7. Project isolation

`project_scope` is mandatory on all four cores. As-of functions require an explicit project scope and filter before returning records. Cross-project retrieval is therefore not an accidental default.

## 8. Migration execution model

`apply_a2_persistence()` deliberately performs two stages:

1. shared base migrations from `db/migrations`;
2. A2 overlay migrations from `db/a2_migrations`.

The base migration installs `pgvector`; the A2 runner verifies the extension exists before applying the overlay. Both baseline and overlay migrations are checksum-registered in `soa_ops.schema_registry`.

## 9. Live execution boundary

This R1 change does **not**:

- connect to the Azure A2 database;
- execute `CREATE EXTENSION vector` live;
- create or change Azure Container Apps resources;
- add VNet/subnets/private endpoints;
- open PostgreSQL public networking;
- alter IAM;
- touch P0 resources/state.

The current Azure database has `vector` **allowlisted**, but the extension is not yet installed in-database.

## 10. Private-connectivity route

The preferred next material route is a dedicated A2 runtime/migration execution path inside the A2 VNet, aligned with the frozen canonical runtime host (Azure Container Apps). Do not expose PostgreSQL publicly to run migrations from a workstation or GitHub-hosted runner.

Before any material Azure change:

`CONTEXT → SYNC → PRECHECK → exact R2 scope → PLAN → VALIDATE → APPLY → RECEIPT`

The material gate must separately authorize any required Container Apps environment/subnet/job/runtime resources. The migration itself must then run from private network reachability and produce a database receipt proving:

- `pg_extension.vector = present`;
- all base migration checksums valid;
- A2 overlay checksum valid;
- four persistence cores present;
- four as-of functions present;
- project isolation and T2→T1 tests PASS.

## 11. Acceptance criteria for this R1 block

- A2 migration overlay isolated from P0 migration directory.
- four persistence cores defined.
- five temporal dimensions preserved.
- mandatory project scope.
- explicit epistemic/admission separation.
- Source→Claim→Memory lineage defined.
- DecisionOS states + R3 human reference guard defined.
- append-only historical mutation guards defined.
- as-of queries require record-time cutoff.
- tests/static CI PASS.
- zero Azure/DB mutation.
