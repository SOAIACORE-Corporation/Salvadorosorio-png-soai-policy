# SOA Intelligence Cognitive Invocation Contract v0.1

**Status:** R1 implementation baseline for `ALPHA-COGNITIVE-LOOP-01`.

## Purpose

Define the provider-neutral boundary between situated SOAiaCore context and a replaceable cognitive engine. Models may reason, infer and hypothesize; their output is classified before any persistence or material action.

## Invocation

`CognitiveInvocationRequest` contains:

- `invocation_id`
- `task_class`
- `messages`
- `context_refs`
- `tool_contracts`
- `output_schema`
- `reasoning_budget`
- `latency_class`
- `privacy_class`
- `max_cost`
- `model_constraints`
- `trace_context`

Provider/model brands are forbidden from the domain contract. Adapter selection is deployment configuration.

## Session Context Buffer

- ephemeral and non-canonical;
- default TTL: 7 days;
- maximum TTL: 30 days;
- project scoped;
- sensitivity and epistemic class travel with each item;
- expired/session purge is explicit and deterministic;
- there is no direct buffer-to-canonical persistence method.

## Context Builder

A context build is situated by `project_scope`, `valid_at`, and `recorded_at`. The builder fails closed on cross-project rows and discards rows recorded after the requested record-time cut. Session items are included only when active, in the same project scope, and before expiration.

The A2 persistence reader remains the authoritative source for canonical memory. The builder adds a second defensive temporal/scope boundary; it does not replace A2 bitemporal semantics.

## Cognitive output policy

Output classes remain explicit:

- `DOCUMENTED_FACT`
- `CONFIRMED_CONTEXT`
- `INFERENCE`
- `HYPOTHESIS`
- `WORKING_ASSUMPTION`
- `STALE_INFORMATION`

Possible dispositions are ephemeral inference, claim proposal, decision proposal, or tool request.

Alpha rules:

1. inference/hypothesis/working assumption never become canonical through this loop;
2. a documented fact without evidence is denied admission;
3. even an evidenced fact is only a claim proposal and still requires the Memory Admission Gate;
4. decision output remains proposed;
5. material tool requests return `HOLD_R2`; this workstream never executes them;
6. receipts are deterministic SHA-256 records and report zero external provider calls in the reference adapter.

## Evaluation binding

The deterministic harness uses the fields and safety invariants from `SOA Intelligence - Evaluation & Golden Dataset Specification v0.1 FINAL`.

Safety failures are non-compensatory. In particular, Alpha requires zero critical T2→T1 leakage, zero cross-project critical memory leakage, and zero R2/R3 action without required authorization.

Semantic/model judging is intentionally outside the first deterministic gate and may be added only as a secondary signal.
