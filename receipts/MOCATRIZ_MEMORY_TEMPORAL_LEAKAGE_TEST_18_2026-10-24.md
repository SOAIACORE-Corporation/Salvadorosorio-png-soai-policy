# MOCATRIZ Test 18 · Memory Temporal Leakage

**Scenario:** SCN-045  
**Status:** PASS · CAPABILITY VALIDATED  
**Validation date:** 2026-10-24

## Claim under test

Historical reconstruction must expose only information that had been recorded by the
requested record-time, even when later versions share the same valid-time.

## Evidence

Validated head:
`b222684cd52accf99fcb7c5c92f10a81e1d7ddae`

CI:
- Landscape Intelligence Schema #264 → SUCCESS
- SOA Intelligence A2 Persistence Static #136 → SUCCESS
- Terraform SOA Intelligence DEV Static #208 → SUCCESS
- SOA Intelligence Alpha Cognitive Loop #71 → SUCCESS
- SOA Intelligence Worker OCI Runtime Smoke #162 → SUCCESS
- PR #84 #532 → SUCCESS

OCI #320 remained a separate security workstream and failed independently.

## Result

PASS.

Disposable PostgreSQL proved record-time isolation across:
- canonical memory;
- episodic temporal memory;
- operational state;
- decision state.

With identical valid-time, T1 queries returned only T1-recorded knowledge. Advancing
recorded_at to T2 exposed T2 without rewriting the earlier knowledge boundary.

No new defect was discovered by this test.

## Canonical consequence

> Una consulta histórica reconstruye lo que podía saberse entonces; conocimiento registrado después no puede viajar hacia atrás en record-time.
