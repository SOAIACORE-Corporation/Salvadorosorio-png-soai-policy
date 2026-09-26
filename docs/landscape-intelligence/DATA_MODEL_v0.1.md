# Landscape Intelligence Data Model v0.1

**Status:** SPECIFIED / validation-gated  
**Authority:** Human decision remains external to the schema.  
**Execution boundary:** This model does not authorize cloud or production changes.

## Purpose

Landscape Intelligence normalizes facts from heterogeneous sources without collapsing their distinct authority.

The canonical flow is:

SOURCE → OBSERVATION → FINDING → DECISION → ACTION → VALIDATION → RECEIPT

Transversal records:

ASSET · DEPENDENCY · COST_SNAPSHOT · IMPACT_ASSESSMENT

## Authority model

- Azure physical state describes observed Azure reality.
- Terraform state describes managed state.
- Terraform plan describes proposed reconciliation, not authorization.
- GitHub IaC describes declarative intent.
- Cost Management describes observed cost for a defined period.
- COMITE / owner records decisions and receipts.
- IA may correlate and recommend; it does not acquire decision authority.

## Core invariants

1. Different does not mean incorrect.
2. UNKNOWN does not mean zero.
3. Observed cost does not mean available budget.
4. A recommendation does not become a decision without explicit authority.
5. A plan does not become an apply.
6. A HOLD is a governed state, not a failed execution.
7. Derived resources can be EXPECTED_DERIVED without being treated as drift.
8. Every material calculation preserves source, period, formula, and confidence.
9. Every material action must be traceable to a decision and validation receipt.
10. Source trust is explicit; derived information never silently becomes authoritative.

## Canonical identity

Assets use a stable canonical asset_id independent of display name.

Recommended provider pattern:

```text
<provider>:<scope>:<native-id>
```

Observations are immutable facts tied to a source and observed time. Findings are adjudicable interpretations over one or more observations.

## Cost semantics

Cost records distinguish:

- observed
- estimated
- avoided
- implementation
- operation
- downtime
- unknown

UNKNOWN is represented with `amount: null`, never with a fabricated zero. Derived or estimated material costs require an explicit formula.

## Impact semantics

Impact is multidimensional. Supported domains:

financial · operation · security · availability · data · compliance · architecture · reputation · continuity

Each domain carries its own 0–4 or UNKNOWN score, rationale, and confidence. No opaque aggregate score is required by the canonical model.

## Initial evidence cases

The v0.1 fixtures exercise the current P0 baseline:

- private PostgreSQL asset
- Service Health ADOPT/CLOSED
- observed SOAiaCore cost
- Terraform global HOLD
- unknown cost visibility gap

The test suite also verifies rejection of:
- observed cost without currency
- estimated material cost without a formula
- decisions without explicit authority

## Acceptance gate

```bash
uv run --frozen pytest -q tests/test_landscape_intelligence_schema.py
```

The GitHub workflow `Landscape Intelligence Schema` runs the same gate on pull requests affecting the schema or its fixtures.

## Next implementation step

The next step is a lightweight collector/normalizer that emits these records from Azure, Terraform, GitHub, Cost Management, monitoring, and application runtime. Collection must remain read-only until a separate execution authority is explicitly approved.
