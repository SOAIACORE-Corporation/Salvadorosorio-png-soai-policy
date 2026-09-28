# SOAiaCore Durable Evidence → Recovery Manifest v0.1

**Status:** IMPLEMENTED / READ-ONLY / TESTABLE

## Purpose

Remove manual status assignment from the Recovery Manifest without allowing the evidence collector to redefine what evidence is required.

```text
REQUIREMENT POLICY
        +
DURABLE EVIDENCE INVENTORY
        ↓
MANIFEST GENERATOR
        ↓
RECOVERY MANIFEST
        ↓
MEMORY INTEGRITY CYCLE
```

## Separation of responsibilities

**Requirement policy** defines what must exist.

**Durable evidence inventory** describes what was actually observed: evidence ID, target requirement, availability, validation state, freshness and source reference.

**Manifest generator** derives `CONFIRMED / PARTIAL / MISSING / STALE / UNKNOWN`.

It cannot create new obligations from evidence and cannot promote missing, stale, partial or unknown evidence to confirmed.

## Canonical absence rule

> No evidence is a visibility state, not a negative fact.

Therefore:
- no available evidence → MISSING;
- stale source → STALE;
- incomplete evidence → PARTIAL;
- unresolved validity → UNKNOWN.

## Integration

`run_memory_cycle_from_evidence()` composes the generator directly with the existing Memory Integrity Cycle.

```text
durable evidence
→ generated Recovery Manifest
→ Context Integrity
→ canonicalization eligibility
→ human/recovery/methodology metrics
→ receipt
```

## Authority boundary

The generator is read-only. It does not rewrite source evidence, create authority, merge, deploy or mutate infrastructure.

## Design rule

The system may automate **evaluation of evidence against policy**.

It may not automate **the policy itself from convenient evidence**.
