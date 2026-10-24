# LANDSCAPE INTELLIGENCE · REGULATORY FRESHNESS v0.1 · 2026-09-26

**Status:** VALIDATED / DETERMINISTIC / FAIL-CLOSED MATERIAL EXECUTION

## Scope

Adds deterministic freshness assessment for canonical regulatory sources using explicit verification timestamps and policy windows.

## States

- CURRENT
- DUE_FOR_REVERIFY
- STALE
- UNKNOWN

Canonical freshness remains current / stale / unknown.

## Rules

- Freshness is derived from `verified_at`, `due_after_hours` and `stale_after_hours`.
- HTTP reachability or page existence does not make a source current.
- DUE_FOR_REVERIFY remains canonically current but requires planned re-verification.
- STALE allows continued analysis but blocks material execution when the regulatory basis is required.
- Missing, invalid or future verification timestamps become UNKNOWN.
- Invalid policy windows fail closed.

## Validation

GitHub Actions workflow: Landscape Intelligence Schema  
Run: #86  
Run ID: 36221595425  
Result: **108 passed in 7.75s**  
Conclusion: SUCCESS

## Safety boundary

No regulatory filing, recall, product release, import/export action, production mutation, Azure mutation, Terraform apply, RBAC mutation or autonomous remediation is authorized by this receipt.

## Next control

Bind freshness policies to the official source registry, expand verified official sources, and generate regulatory Decision Cases whose execution gates consume the freshness assessment.
