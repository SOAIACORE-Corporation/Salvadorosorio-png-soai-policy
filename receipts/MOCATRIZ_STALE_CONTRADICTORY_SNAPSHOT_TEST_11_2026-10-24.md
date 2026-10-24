# MOCATRIZ Test 11 · Stale / Contradictory Snapshot Authority

**Scenario:** SCN-038  
**Error:** ERR-20261024-039  
**Status:** PASS  
**Validation date:** 2026-10-24

## Claim under test

When several Trusted Memory Snapshots are individually valid, authority must be selected
by non-ambiguous lineage and temporal validity, not by latest timestamp, version number,
field count or apparent completeness.

## Control implemented

`select_authoritative_snapshot(...)` now:

- filters by logical snapshot identity;
- requires valid FROZEN/CANONICAL artifacts;
- applies historical `as_of` validity;
- selects the unique lineage head;
- rejects duplicate version conflicts;
- rejects lineage forks;
- rejects missing trusted-memory predecessors;
- rejects temporal/version lineage inversions.

## Evidence

Control head:
`974bd924bfa572302956b6055ae4793118d5c291`

CI:
- Landscape Intelligence Schema #222 → SUCCESS
- SOA Intelligence A2 Persistence Static #94 → SUCCESS
- Terraform SOA Intelligence DEV Static #166 → SUCCESS
- SOA Intelligence Alpha Cognitive Loop #29 → SUCCESS
- SOA Intelligence Worker OCI Runtime Smoke #120 → SUCCESS

OCI #278 remains a separate security workstream.

## Result

PASS. ERR-20261024-039 is CONTROLLED.

## Canonical consequence

> La versión más nueva o más completa no es necesariamente la autoridad vigente; la autoridad exige lineage temporal no ambiguo.
