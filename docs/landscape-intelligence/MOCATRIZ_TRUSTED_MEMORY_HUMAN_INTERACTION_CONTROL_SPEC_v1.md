# MOCATRIZ · Trusted Memory · Human Interaction Control Specification v1

**Status:** CANDIDATE / TESTABLE  
**Branch:** `feat/landscape-intelligence-data-model-v1`  
**PR:** #84 OPEN / DRAFT

## Objective

Define one integrated control surface for adaptive execution, interruption recovery, Trusted Memory fidelity, bitemporal persistence and efficient human escalation.

## Architecture

```text
OBJECTIVE
→ MOCATRIZ (OBSERVE → UNDERSTAND → RESOLVE → DEMONSTRATE)
→ durable evidence
→ Recovery Manifest + Context Integrity
→ Trusted Memory Snapshot
→ bitemporal persistence
→ blind reconstruction / fidelity
→ Preflight Completeness / Human Interaction Efficiency
→ receipt / closure
```

## Functional controls

1. **Continuity:** external execution continuity does not imply task continuity.
2. **Fidelity:** recovered state must preserve objective, checkpoint, rules, exceptions, pending items and resume point.
3. **Persistence:** TMS versions are written/read through the existing A2 bitemporal schema in ephemeral CI PostgreSQL.
4. **Predecessor semantics:** only a persisted TMS predecessor populates `supersedes_memory_id`; historical CHK-* predecessors remain lineage metadata.
5. **Human interaction:** all required machine-verifiable preconditions must be checked before material human action.
6. **Error learning:** every material failure remains append-only evidence, with prevention rule and regression test where possible.
7. **Security:** a lateral security regression remains explicit and fail-closed; it is not hidden to make another objective appear green.

## Code

- `tools/landscape/mocatriz_execution.py`
- `tools/landscape/mocatriz_continuity.py`
- `tools/landscape/trusted_memory.py`
- `tools/landscape/human_interaction.py`
- `tools/landscape/memory_cycle.py`
- `tools/landscape/error_register.py`
- `tools/landscape/error_control_audit.py`
- `db/a2_migrations/1001_memory_decision_bitemporal.sql`

## Tests

- `schemas/tests/test_mocatriz_continuity.py`
- `schemas/tests/test_trusted_memory_tms002.py`
- `schemas/tests/test_human_interaction_efficiency.py`
- `schemas/tests/test_error_control_closure.py`
- `tests/test_a2_persistence_contract.py`

## Metrics

- Human Interaction Efficiency = necessary / total.
- Avoidable Human Interaction Rate = avoidable / total.
- 0/0 = `NOT_EXERCISED`.
- Recovery Efficiency excludes non-recoverable authority events.
- Control Yield and Methodological Overhead remain separate.

## Authority

This specification grants no merge, production mutation, Terraform apply/destroy, security exception, firewall change or deployment authority.


## Human Authority Integrity · validated extension 2026-10-24

The Human Interaction control surface is now materially stronger than simple four-part
correlation. The following invariants are implemented and tested in ephemeral PostgreSQL:

1. **Durable cross-session Human Task** — WAITING_HUMAN survives transient context loss.
2. **Single authoritative response** — replay/conflicting second responses fail closed.
3. **Temporal validity** — REVOKED / SUPERSEDED / EXPIRED tasks reject later responses.
4. **Project isolation** — project_scope is part of durable response/lifecycle correlation.
5. **Bitemporal authority recovery** — later-recorded evidence can invalidate current
   authority without rewriting historical knowledge.
6. **Concurrent execution isolation** — response arrival order cannot cross-bind
   simultaneous Human Tasks.
7. **Durable responder provenance** — new responses require responder_ref,
   authority_level and authentication_ref.

### Canonical Human Task rule set

A Human Task response is resume-eligible only when all of the following are true:

```text
task identity matches
+ execution identity matches
+ correlation identity matches
+ project scope matches
+ task remains temporally valid
+ no competing authoritative response exists
+ current bitemporal reconstruction still considers the response authoritative
+ durable responder/authentication provenance exists
```

Correlation alone is therefore necessary but insufficient.

### Persistence artifacts

- `db/a2_migrations/1002_mocatriz_human_task_resume.sql`
- `db/a2_migrations/1003_mocatriz_human_response_replay_guard.sql`
- `db/a2_migrations/1004_mocatriz_human_task_lifecycle_guard.sql`
- `db/a2_migrations/1005_mocatriz_human_task_project_scope_guard.sql`
- `db/a2_migrations/1006_mocatriz_human_task_authority_asof.sql`
- `db/a2_migrations/1007_mocatriz_human_response_provenance.sql`

### Validated scenarios

| Test | Scenario | Result | Primary CI evidence |
|---|---|---|---|
| 03 | SCN-030 · Durable cross-session resume | PASS | A2 #73 |
| 04 | SCN-031 · Response replay/conflict | PASS | A2 #74 |
| 05 | SCN-032 · Stale human authority | PASS | A2 #76 |
| 06 | SCN-033 · Cross-project authority isolation | PASS | A2 #78 |
| 07 | SCN-034 · Late-recorded backdated revocation | PASS | A2 #80 |
| 08 | SCN-035 · Concurrent Human Task isolation | PASS | A2 #81 |
| 09 | SCN-036 · Human response provenance gate | PASS | A2 #82 |

All tests use disposable CI PostgreSQL and preserve the no-live-cloud mutation boundary.

### Explicit boundary

`authentication_ref` proves that durable provenance points to authentication evidence;
it does not make PostgreSQL an identity provider. End-to-end cryptographic verification
of the human actor remains a separate integration test.

### Derived rules

> Correlación correcta no implica autoridad vigente.

> La autoridad correlacionada también tiene ámbito.

> Nueva evidencia puede invalidar autoridad vigente sin reescribir lo que históricamente se sabía.

> Una respuesta correlacionada no es autoridad durable si no conserva quién respondió y qué evidencia autentica esa autoridad.
