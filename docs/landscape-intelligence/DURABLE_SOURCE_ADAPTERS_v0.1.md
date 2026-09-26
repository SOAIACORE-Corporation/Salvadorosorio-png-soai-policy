# SOAiaCore Durable Source Adapters v0.1

**Status:** IMPLEMENTED / READ-ONLY / TESTABLE

## Purpose

Normalize heterogeneous durable sources into the evidence inventory consumed by the Recovery Manifest generator.

Supported source kinds:
- git_commit
- ci_run
- receipt
- snapshot
- decision

## Semantic rule

Source outcome and evidence quality are different dimensions.

A completed CI run whose conclusion is failure can still be **CONFIRMED evidence** that validation failed.

The adapter therefore preserves:
- source kind
- source reference
- source outcome
- retrieval completeness
- freshness
- explicit requirement binding

## Requirement binding

A source MUST declare the requirement it is intended to satisfy.

The adapter does not infer that:
- a commit proves authority;
- a receipt proves causality;
- a CI run proves a decision;
- a decision proves freshness.

Meaning is bound explicitly by policy/extractor context.

## E2E path

```text
HETEROGENEOUS DURABLE SOURCES
→ SOURCE ADAPTERS
→ EVIDENCE INVENTORY
→ RECOVERY MANIFEST GENERATOR
→ MEMORY INTEGRITY CYCLE
```

## Freshness

Freshness is derived only when:
- an observed timestamp exists;
- a maximum allowed age is declared;
- an `as_of` timestamp is supplied.

A stale source remains valid evidence of an old state but does not become current evidence.

## Authority boundary

Adapters are read-only and do not create authority, mutate source systems, merge, deploy or remediate.
