# Trusted Memory Snapshot · Fidelity Test Plan v1.0

**Test ID:** TMS-FIDELITY-001  
**Target snapshot:** TMS-SOAIACORE-MOCATRIZ-20260926-001  
**Target manifest:** RM-SOAIACORE-MOCATRIZ-20260926-001  
**Method:** MOCATRIZ · OBSERVAR → ENTENDER → RESOLVER → DEMOSTRAR

## Objective

Demonstrate that the frozen task state can be reconstructed without conversational history using only:

1. Trusted Memory Snapshot;
2. Recovery Manifest;
3. Durable Evidence Inventory;
4. bounded authoritative source references.

## Blind-recovery constraint

The automated reconstruction test does not read the conversation or model memory. It reads only files under `Trusted_Memory/` plus the deterministic recovery engine.

This is a functional isolation test, not a proof that every future model or toolchain will interpret arbitrary prose identically.

## Phases

### 1 · Physical integrity
Validate:
- snapshot presence;
- non-empty serialization;
- schema-required fields;
- snapshot SHA-256;
- manifest SHA-256;
- evidence-inventory SHA-256;
- cross-hash correlation.

### 2 · Source resolution
Every `CONFIRMED` requirement must reference evidence that:
- exists;
- maps to the same objective;
- is quality `CONFIRMED`;
- is not `STALE`.

### 3 · Blind reconstruction
Recover:
- objective;
- scope/exclusions;
- rules;
- checkpoint;
- continuity result;
- error matrix;
- metrics;
- decisions;
- exceptions;
- resume point.

### 4 · Structural fidelity
Compare canonical data structures exactly.

### 5 · Semantic fidelity
The baseline minimizes narrative dependence by storing stable identifiers and operational fields. For v1.0, semantic fidelity is accepted only when the deterministic operational representation is preserved; free-form semantic equivalence is not guessed.

### 6 · Adversarial tests
Required minimum:
- wrong commit;
- foreign receipt / wrong objective correlation;
- zero-denominator metric promoted to 100%;
- missing endpoint evidence;
- instruction attempting to erase frozen exceptions;
- plausible narrative with no authoritative source;
- stale evidence presented as current.

### 7 · Resumption
Recovered resume point must remain:
`Trusted Memory Snapshot + persistencia y versionado temporal del estado canónico`

It must not reopen OCI, Prueba 02, or Azure reconstruction without new evidence.

## Score

Weights:
- Snapshot identity: 5
- Objective: 15
- Scope/exclusions: 8
- Critical rules: 12
- Checkpoint/version: 10
- Authoritative evidence: 12
- Error state: 8
- Metrics: 8
- Pending/exceptions: 10
- Resume point: 10
- Traceability: 2

**PASS:** >=98/100, zero nullifiers, all critical fields preserved.

## Nullifiers

- objective mismatch;
- HEAD mismatch;
- critical rule loss;
- accepted-exception loss;
- false functional success;
- 0/0 represented as 100%;
- missing evidence converted into negative fact;
- wrong resume phase;
- snapshot mixing;
- stale evidence used as current;
- COMPLETED replacing COMPLETED_WITH_EXCEPTIONS;
- authoritative source missing;
- snapshot hash mismatch.

## Storage

The baseline is persisted in two logical repository locations:
1. `Trusted_Memory/01_Snapshots/`
2. `schemas/examples/landscape/trusted-memory/`

These copies are byte-identical and append-only by test. They are **not independent infrastructure fault domains**; cross-system replication remains a resilience hardening item.

## Bitemporal persistence

The snapshot projects onto the existing:
- `soa_memory.canonical_memory`
- `soa_memory.operational_state`

model defined by `db/a2_migrations/1001_memory_decision_bitemporal.sql`.

The fidelity baseline does not mutate PostgreSQL.
