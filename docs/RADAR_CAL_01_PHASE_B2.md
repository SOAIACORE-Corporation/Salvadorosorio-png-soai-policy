# SOAiaCore · RADAR-CAL-01 · Phase B2

Status: COMPLETE / RETROSPECTIVE CONTROLLED
Date: 2026-08-18

## Goal
Stress-test the flexible psychosocial inference standard at structural scale: triads, episodic convergence and network brokerage.

## Protocol
1. Read F5 Microsequences without opening F5 Validation.
2. Freeze 24 predictions in the calibration register (`RADAR_CAL_01_B2_PRE`).
3. Open F5 Validation only after freeze.
4. Score 9 directly comparable structures.
5. Inspect F5 Centrality and F5 Blocks post-hoc only to diagnose structural misses.

## Results
- Rigid exact categorical match: 4/9 = 44.4%
- Flexible exact categorical match: 5/9 = 55.6%
- Mean ordinal distance (REJECT=0, PARTIAL=0.5, CONFIRM=1): rigid 0.333; flexible 0.222
- Within one ordinal step: rigid 8/9 = 88.9%; flexible 9/9 = 100%

## Main finding
Flexible inference improved pragmatic calibration, but local conversational windows under-detected structural brokerage. Three misses/underestimates clustered in brokerage structures:
- Abdiel · SOA · Aleso
- SOA · Aleso · Luis Rodrigo
- Abdiel · SOA · PHILLIPPE

Post-hoc F5 Centrality data show SOA with betweenness 0.46667, degree 16, PageRank 0.13287 and cross-block participation 0.607 across three blocks. Therefore the relevant phenomenon is topological/longitudinal, not necessarily an overt act inside one microsequence.

## Architectural correction
Use a multi-layer inference route:

`MICROSEQUENCE → LONGITUDINAL PATTERN → NETWORK/TOPOLOGY → ROLE CONTEXT → INFERENCE → CONTRADICTION → CONFIDENCE → REVISION`

Do not use network position to infer hidden intent, private alliance, affect or diagnosis. Distinguish episodic coalition from stable coalition, and conscious mediation from structural brokerage.

## Limitations
Retrospective, small sample, corpus-specific human reference, and simplified three-level scoring. The network layer was used post-hoc for diagnosis, not to inflate precommitted scores.

## Next gate
B3 must freeze predictions after integrating all three layers before adjudication: microsequence + longitudinal + network.