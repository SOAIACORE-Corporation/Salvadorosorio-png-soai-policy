# SOAIACORE Canonical Persistence Model v1.0

**Architecture binding:** SOAIACORE Architecture v0.6 FINAL / FROZEN FOR P0

**Implementation line:** AR v0.8

**Status:** DESIGN BASELINE / LOCAL-FIRST / NO CLOUD DEPLOYMENT

**Canonical persistence:** PostgreSQL + pgvector

**Provider binding:** provider-neutral domain model; Azure is P0 integration binding only.

## 1. Purpose

This model fixes the canonical persistence domains, table responsibilities, identity/evidence lineage,
maturity boundaries and migration rules for P0 while preserving development freedom.

It does **not** freeze every physical index, storage parameter or cloud SKU.

## 2. Maturity model

Per Architecture v0.6 FINAL:

- `M0 EXPERIMENTAL` — exploratory implementation/data/contract state.
- `M1 CANDIDATE` — candidate for canonical review.
- `M2 CANONICAL` — accepted canonical schema/contract/data representation.
- `M3 PRODUCTION_FROZEN` — production-frozen representation when production exists.

`E0-E5` is reserved for epistemic levels. Maturity and epistemic labels must never share semantics.

## 3. PostgreSQL logical namespaces

| Namespace | Role | P0 maturity |
|---|---|---|
| `soa_core` | project/corpus/context/claims/relations | M2 target |
| `soa_identity` | observed actors, canonical subjects, aliases, identity decisions | M2 target |
| `soa_evidence` | sources, evidence objects, transforms, references | M2 target |
| `soa_intelligence` | profiles, authorization, registries, runs, model/tool execution, embeddings | M1→M2 |
| `soa_adjudication` | ratings, adjudication, ground truth | M2 target |
| `soa_ops` | jobs, receipts, schema registry, cost/teardown metadata | M1→M2 |
| `experimental` | disposable/rebuildable experiment structures | M0 |

## 4. Canonical table set

### soa_core
- `projects`
- `corpora`
- `contexts`
- `context_capsules`
- `relationships`
- `claims`
- `claim_relations`
- `claim_evidence`
- `context_graph_edges`

### soa_identity
- `observed_actors`
- `canonical_subjects`
- `aliases`
- `identity_claims`
- `identity_decisions`

### soa_evidence
- `source_artifacts`
- `evidence_objects`
- `evidence_transforms`
- `evidence_references`

### soa_intelligence
- `analysis_profiles`
- `authorization_decisions`
- `calibration_registry`
- `external_source_registry`
- `runs`
- `model_runs`
- `tool_runs`
- `embeddings`

### soa_adjudication
- `adjudications`
- `adjudication_ratings`
- `ground_truth_ledgers`
- `ground_truth_items`

### soa_ops
- `jobs`
- `context_receipts`
- `deployment_receipts`
- `schema_registry`

## 5. Canonical rules

1. Object bytes stay outside PostgreSQL by default.
2. Provider IDs are external references, never canonical primary identity.
3. Names/emails/phones are never canonical keys.
4. `observed_actor != canonical_subject != civil_identity`.
5. Identity merge/split decisions are append-only and reversible.
6. `NEVER_MERGE` is a strong identity constraint.
7. Evidence states remain explicit and cannot be silently elevated.
8. Claims must retain evidence/counterevidence links and epistemic labeling.
9. `claim_kind` and `epistemic_class` are independent.
10. `confidence_score` is not probability unless semantics/calibration are declared.
11. ContextGraph is a logical interface; P0 storage is PostgreSQL adjacency/temporal edges.
12. Human review is policy-driven: NONE / OPTIONAL / REQUIRED.
13. Ground truth records the protocol that created it; human adjudication is one path, not the only path.
14. M0 experimental structures cannot overwrite M2/M3 canonical history.
15. Any destructive M2/M3 schema change requires a versioned migration and rollback/restore plan.

## 6. Development freedom

`experimental.*` may be created, altered, dropped and rebuilt freely.

Allowed:
- new feature tables;
- temporary model outputs;
- alternate feature vectors;
- experimental graph representations;
- temporary classifications;
- benchmark-only indexes.

Not allowed:
- mutating canonical identity history without an IdentityDecision;
- overwriting canonical evidence lineage;
- deleting receipt history as an ordinary experiment;
- promoting experimental claims to canonical without a governed migration/promotion path.

## 7. Extension points

Canonical tables use strong relational columns for invariants and `jsonb` for bounded extensibility.

Examples:
- profile configuration;
- methodology-specific parameters;
- provider metadata;
- model generation configuration;
- evidence modality metadata;
- context dimensions;
- calibration metadata.

An experimental JSON key becomes a strong canonical column only after repeated cross-profile value and migration review.

## 8. ContextGraph P0

Reference implementation:
- `soa_core.context_graph_edges`
- directed or undirected semantic edge represented explicitly;
- temporal validity;
- source/provenance reference;
- optional confidence/weight;
- recursive SQL queries for traversal.

No Neo4j/graph DB is canonical in P0.

## 9. pgvector placement

`soa_intelligence.embeddings` stores selective embeddings only.

Required dimensions:
- embedding_id
- owner_type / owner_id
- model_id / model_version
- vector
- source evidence/context reference when applicable
- created_at
- metadata

No raw-corpus embed-everything default.

## 10. Production freeze rules

When M3 exists:
- schema migrations only through reviewed migration files;
- no ad-hoc DDL;
- no destructive migration without backup/restore evidence;
- append-only historical identity/evidence/receipt semantics;
- compatibility window required for application releases;
- rollback or forward-fix plan required.

## 11. Environment model

P0 has no permanent DEV/QA/STAGING/PROD cloud duplication.

- Day-to-day: local PostgreSQL + pgvector.
- Azure: bounded/ephemeral integration and benchmark environment.
- Production: not created.

Git migrations + fixtures + schemas are the portable source of truth.
