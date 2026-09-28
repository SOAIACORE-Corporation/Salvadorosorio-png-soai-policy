# SOAiaCore Regulatory Canonical Layer v0.1

## Purpose

Provide a continuously verifiable regulatory basis for Landscape Intelligence so analysis can continue without relying on model memory, while material execution remains gated by current authoritative evidence.

Canonical chain:

REGULATORY_SOURCE → REGULATORY_ASSERTION → APPLICABILITY_ASSESSMENT → SCENARIO → DECISION_CASE

## Source classes

### Binding
Examples:
- laws
- regulations
- mandatory standards where legally applicable

### Authoritative guidance
Official regulator guidance that explains current agency thinking but is not silently promoted to binding law.

### Standard / compendial
Pharmacopoeial, technical, or industry standards whose legal effect depends on jurisdiction and incorporation.

### Internal control
Corporate policy, architecture rule, or operating control.

## Source tiers

1. TIER_1_OFFICIAL_MACHINE_READABLE
2. TIER_2_OFFICIAL_NAVIGABLE
3. TIER_3_LICENSED_STANDARD
4. TIER_4_EXPERT_INTERPRETATION

The engine must know which tier supports each claim.

## Freshness semantics

Canonical source freshness remains:
- current
- stale
- unknown

The deterministic assessment layer additionally exposes:
- CURRENT
- DUE_FOR_REVERIFY
- STALE
- UNKNOWN

Freshness is derived from `verified_at` plus explicit policy windows (`due_after_hours`, `stale_after_hours`). HTTP reachability or page existence never makes a regulatory source current by itself.

`DUE_FOR_REVERIFY` is intentionally distinct from `STALE`: the source remains canonically current but its verification window is approaching the stale boundary. A stale/unknown regulatory basis does not shut down cognition.

It does:
- permit analysis,
- mark uncertainty,
- require refresh/review,
- block material execution when the regulatory basis is required.

A future, missing or invalid verification timestamp becomes UNKNOWN and fails closed for material execution.

## Exception semantics

Internal controls:
- may be modeled for exception,
- exception authority = SOA / Salvador Osorio Ayala.

External binding obligations:
- NON_WAIVABLE_EXTERNAL,
- cannot be overridden by an internal exception authority,
- SOA may authorize only a lawful internal response/temporary control deviation that does not purport to waive external law.

## Initial canonical sources

### US · 21 CFR Part 211
Official current eCFR source.
Binding regulation.
Use for CGMP obligations affecting finished pharmaceuticals.

### US · FDA Data Integrity and Compliance With Drug CGMP
Official FDA guidance.
Authoritative guidance; not silently converted into binding law.

### MX · NOM-059-SSA1-2015 + official modification
Official DOF source.
Binding standard, with amended state preserved.

## Adversarial scenario handling

A scenario statement is not automatically a legal fact.

Claims such as:
- "this is automatically a crime",
- "this always requires recall",
- "the regulator will certainly impose X",
- "this contract is void",

must enter as unverified scenario claims and then be adjudicated against canonical regulatory sources.

Possible applicability outcomes:
- YES
- NO
- PARTIAL
- UNKNOWN

Decision states:
- SUPPORTED
- REQUIRES_REVIEW
- CONTRADICTED
- UNKNOWN

## Execution gate

For material actions involving recall, regulatory filing, import/export release, product release, destruction, disclosure, or other regulated execution:

- missing basis → REGULATORY_VISIBILITY_GAP
- stale/unknown basis → REGULATORY_REVIEW_REQUIRED
- current basis → REGULATORY_BASIS_CURRENT

Current basis does not itself authorize execution; normal authority and exception gates still apply.
