# SOAiaCore Context Integrity & Recovery Confidence v0.1

**Status:** SPECIFIED / TESTABLE / READ-ONLY  
**Purpose:** Convert context continuity from an intuition into an auditable control.

## Problem

A conversational AI may lose part of the narrative while durable artifacts still preserve the actual state. SOAiaCore must detect that discontinuity, reconstruct only what evidence supports, expose what remains unknown, and quantify the quality of the reconstruction.

The metric is **not** "AI certainty." It is **evidentiary continuity**.

## Canonical recovery chain

LAST TRUSTED SNAPSHOT
→ RECOVERED SOURCES
→ RECOVERED FACTS
→ RECOVERED DECISIONS
→ CAUSAL LINKS
→ VALIDATIONS / RECEIPTS
→ CURRENT TRUSTED SNAPSHOT

Missing material must remain explicit:

- RECOVERED_FACT
- RECOVERED_DECISION
- INFERRED_SEQUENCE
- UNRECOVERED_GAP
- VERBATIM_DIALOGUE_UNRECOVERED

## Context Integrity Score

Five dimensions, all explicit and independently inspectable:

| Dimension | Weight |
|---|---:|
| Evidence coverage | 30% |
| Causal continuity | 25% |
| Authority integrity | 20% |
| Source freshness | 15% |
| Receipt integrity | 10% |

Each dimension is:

`confirmed / expected`

Overall raw score:

`Σ(dimension_ratio × dimension_weight)`

No language-model self-rating enters the formula.

## Confidence bands

- 95–100: VERIFIED_CONTINUITY
- 85–94.99: HIGH_CONFIDENCE
- 70–84.99: PARTIAL_CONTINUITY
- 50–69.99: DEGRADED_CONTINUITY
- <50: UNRELIABLE_CONTINUITY

## Fail-closed claim ceilings

A high arithmetic score cannot hide a critical provenance failure.

- Missing required authority → claimable confidence capped at **84%**.
- Missing primary evidence for a material transition → capped at **69%**.
- Missing verbatim dialogue is disclosed but does not reduce state confidence when facts, decisions, rationale and receipts are independently recoverable.

These ceilings are explicit policy, not hidden heuristics.

## Interpretation

A 96% Context Integrity Score means:

> 96% of the required evidentiary continuity model is satisfied under the declared policy.

It does **not** mean:

> there is a 96% probability that every AI statement is true.

Factual correctness still depends on each source and claim.

## Authority boundary

Confidence never grants:
- execution authority,
- exception authority,
- permission to merge,
- permission to apply Terraform,
- permission to mutate Azure,
- permission to reinterpret external binding obligations.

## Initial mandatory scenarios

### SCN-021 · Context / History Gap

A time window of conversation is unavailable between two trusted states.

Required behavior:
- detect the discontinuity;
- freeze current baseline;
- recover durable artifacts;
- distinguish recovered fact from inferred sequence;
- publish Context Integrity Score;
- never invent missing dialogue.

### SCN-022 · State exists, rationale missing

Technical state and receipts exist, but decision rationale is absent.

Required behavior:
- preserve the state as observed;
- open a rationale visibility gap;
- reduce causal/decision continuity accordingly;
- never reconstruct motive as fact.

## Operational objective

For committee-grade continuity, target:

- **≥95% claimable Context Integrity**, and
- **zero critical gates** involving missing authority or missing material primary evidence.

Anything below the target remains usable for analysis, but the system must expose the degraded confidence before relying on it for a material decision.
