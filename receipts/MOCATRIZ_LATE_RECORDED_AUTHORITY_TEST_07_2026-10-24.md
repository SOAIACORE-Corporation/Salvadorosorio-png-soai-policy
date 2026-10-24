# MOCATRIZ Test 07 · Late-Recorded Backdated Revocation

**Scenario:** SCN-034  
**Error:** ERR-20261024-036  
**Status:** PASS  
**Validation date:** 2026-10-24

## Claim under test

Later-recorded evidence may prove that a Human Task was already invalid at the time a
previously accepted response arrived. SOAiaCore must preserve the historical response
while removing it from current resume authority.

## Evidence

Commit:
`fe4fe04f88b88dedeca2af167624e6736481e6d8`

CI:
- Landscape Intelligence Schema #208 → SUCCESS
- SOA Intelligence A2 Persistence Static #80 → SUCCESS
  - Run A2 persistence contract tests → SUCCESS
  - Enforce no live-cloud boundary → SUCCESS

## Result

PASS.

At the earlier recorded-time boundary the response is reconstructed as AUTHORITATIVE.
After later evidence is recorded with an earlier effective_time, current recovery returns
authority_state=INVALIDATED, response=null and preserves the original answer as
invalidated_response with explicit lifecycle lineage.

## Canonical consequence

New evidence may change current authority without falsifying what the system historically knew.
