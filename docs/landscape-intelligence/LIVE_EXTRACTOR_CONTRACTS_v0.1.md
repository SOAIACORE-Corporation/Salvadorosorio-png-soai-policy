# Landscape Intelligence Live Extractor Contracts v0.1

**Status:** DESIGN CONTRACT / NO LIVE EXECUTION AUTHORITY

## Objective

Define the minimum read-only contract required to connect live sources without widening operational authority.

Every extractor must:
1. read only,
2. declare source authority,
3. preserve source timestamps,
4. preserve native identity,
5. emit canonical records,
6. expose freshness,
7. fail closed on missing permissions,
8. never mutate the source system,
9. never silently coerce UNKNOWN to zero,
10. produce provenance sufficient for independent validation.

## Extractor contracts

### Azure physical state
Input authority: Azure Resource Manager / resource provider APIs.
Required permission: read-only resource inventory and selected configuration reads.
Output: asset + observation.
Forbidden: PUT/PATCH/DELETE, RBAC mutation, deployment.

### Azure Cost Management
Input authority: Cost Management query results.
Required permission: cost read.
Output: cost_snapshot.
Required semantics: period, currency, observed vs estimated.
Forbidden: interpreting budget as balance.

### Terraform State
Input authority: remote state.
Required permission: controlled read.
Output: observation.
Forbidden: state mutation, import, rm, apply.

### Terraform Plan
Input authority: generated plan artifact.
Output: finding/observation.
Forbidden: apply.
Rule: plan != authorization.

### GitHub IaC
Input authority: repository commit/tree.
Required permission: contents read.
Output: observation of declarative intent.
Forbidden: branch mutation, merge.

### GitHub PR
Input authority: pull request metadata/reviews.
Required permission: PR read.
Output: observation.
Rule: PR state != Decision Record.

### Monitoring
Input authority: metrics/alerts.
Required permission: metrics/alerts read.
Output: observation/finding.
Required: window, unit, source semantic for NoData.
Forbidden: treating 0 as healthy without semantic evidence.

### Security / RBAC
Input authority: IAM role assignments/policies.
Required permission: IAM read.
Output: observation.
Forbidden: role grant/revoke.
Rule: broad access visibility may open a PENDING case, never auto-remove.

### Application runtime
Input authority: health/version/dependency endpoint or telemetry.
Required permission: read-only health metadata.
Output: observation + derived dependency.
Forbidden: restart/redeploy.

### COMITE / Drive
Input authority: explicit committee/owner records.
Required permission: document read.
Output: decision/receipt only when authority and rationale are explicit.
Forbidden: converting notes/recommendations into decisions.

## Failure semantics

An extractor failure is itself information:
- AUTH_FAILED
- SOURCE_UNAVAILABLE
- STALE
- PARTIAL
- SCHEMA_REJECTED
- UNKNOWN

Extractor failure must never be replaced with an empty "healthy" result.

## Adoption sequence

1. file fixture
2. local read-only adapter
3. CI contract tests
4. live read-only extraction in non-production context
5. compare fixture vs live shape
6. controlled scheduled extraction
7. historical retention
8. only then consider persistence scale-up

No step grants execution authority.
