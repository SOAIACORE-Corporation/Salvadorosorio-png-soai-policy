# Landscape Intelligence · Temporal Decision Intelligence Receipt

**Date:** 2026-09-26  
**Branch:** `feat/landscape-intelligence-data-model-v1`  
**PR:** #84  
**Status:** VALIDATED / EXPLAINABLE / NO HIDDEN THRESHOLDS

## Capability

Historical patterns can now become committee-ready Decision Cases without converting pattern detection into execution authority.

Supported temporal patterns:

- PERSISTENT_FINDING
- REPEATED_VISIBILITY_GAP
- MONOTONIC_COST_INCREASE

## Materiality model

Financial materiality is never invented by the engine.

If no explicit policy is supplied:

- delta is calculated,
- percentage is calculated where possible,
- materiality remains `NO_POLICY`,
- no threshold is silently assumed.

If evidence is incomplete:

- state = `UNKNOWN`,
- materiality remains unset.

## Temporal Decision Cases

Examples:

Persistent finding:
- MAINTAIN
- INVESTIGATE
- PREPARE_CHANGE

Repeated visibility gap:
- ACCEPT_GAP
- CLOSE_GAP

Monotonic cost increase:
- OBSERVE
- DEFINE_MATERIALITY
- INVESTIGATE_DRIVERS

Alternatives remain non-ranked.

## Acceptance evidence

GitHub Actions:

`Landscape Intelligence Schema · run #50`

Result:

```text
64 passed in 4.15s
```

## Execution boundary

No Azure mutation.  
No Terraform apply.  
No RBAC mutation.  
No PostgreSQL write.  
No production deployment.  
No autonomous remediation.

## Adjudication

F4 file-based history is validated as the current low-cost persistence baseline.

PostgreSQL remains conditional on demonstrated scale, concurrency, query, or retention needs.
