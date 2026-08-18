# SOAiaCore · RADAR-CAL-01 · Phase B4 HOLDOUT

Status: COMPLETED · RETROSPECTIVE CONTROLLED HOLDOUT
Date: 2026-08-18

## Objective
Test the multilayer/multiaxial engine on a relational source pair not previously inspected in this calibration sequence, freezing predictions before opening the P2-P3 validation layer.

## Design
PRE source: `FratMX · P1-P2 · Confianza Alianzas y Bloques v1`.
POST/gold source: `FratMX · P2-P3 · Validación Relacional Profunda v1`.

16 claims were frozen in `RADAR_CAL_01_B4_HOLDOUT_PRE`. Fourteen were scorable after excluding one target-mismatch claim and one unvalidated dyad.

## Results
- Exact semantic/band alignment: 9/14 (64.3%).
- Partial directional alignment: 4/14 (28.6%).
- Material failure: 1/14 (7.1%).
- Exact + partial: 13/14 (92.9%).

These are internal descriptive holdout results, not population estimates. Alignment adjudication was performed by the same system and requires independent replication.

## Key falsification
`Abdiel ↔ Carlo Flores` showed structural trust 95.22 and institutional alignment 97.23 in P1-P2. A scalar model predicted high operational trust. P2-P3 operational trust was 48.80, with positive reciprocity 0 and positive share 0.13.

Therefore:

**STRUCTURAL TRUST ≠ OPERATIONAL TRUST**

This is the principal B4 model correction.

## TRUST_VECTOR
`TRUST_VECTOR = [trust_structural, operational_trust, positive_reciprocity, positive_share, explicitness, positive_evidence, persistence, repair_resilience]`

Rules:
- structural trust is not a proxy for operational trust;
- total reciprocity is not positive reciprocity;
- traffic/mentions/transitions are not trust;
- operational trust is not intimacy/friendship/private loyalty;
- repair requires contextual sequence;
- absence of validated signal is not zero.

## Positive holdout signals
- `SOA ↔ Abdiel`: high structural relation and asymmetry were correctly anticipated, while operational level was overcalled.
- `SOA ↔ Philippe`: P2-P3 confirmed cleaner reciprocal operational confidence than SOA↔Abdiel despite lower structural trust.
- `SOA ↔ Solis`: medium/non-exclusive bridge interpretation was retained.
- SOA as a network role: P2-P3 explicitly supports `bisagra`, not unique center.
- P2-P3 explicitly states that power and trust must be analyzed by layers.

## Protocol incident
A prior F9 sparse-candidate branch was not scored because candidate IDs did not map directly to the 12 microvalidated units. The branch is retained as a design failure: PRE and GOLD must share unit identity. B4 was restarted on P1-P2 → P2-P3 with a new freeze before reading POST content.

## Governance impact
B4 is additive. It does not modify DecisionOS v0.3-SHADOW-FROZEN, SOA_CONTEXT routing, PRECHECK, change locks, approval gates, or production state.

## Next gate: B5
Pre-register units and labels, use independent/double-blind adjudication where feasible, score calibration by vector dimension, and add Brier/log-loss when explicit probabilities are emitted.
