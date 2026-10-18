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
