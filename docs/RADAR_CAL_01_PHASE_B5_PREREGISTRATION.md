# SOAiaCore · RADAR-CAL-01 · Phase B5 Preregistration

Status: PREREGISTERED / ADJUDICATION PENDING
Date: 2026-08-18

## Purpose
B5 is the investment decision gate for the flexible, multi-layer, multi-axial psychosocial inference engine. It is not another retrospective demonstration.

## Frozen design
- Minimum evaluable units: 48.
- Stratified holdout across salience, cooperative/conflict/ambiguous contexts, and dyadic/network/role scales.
- Two independent adjudicators.
- Raters blinded to model probability/confidence, previous adjudications, actor rankings and prior phase results.
- Model freezes, per unit: construct, categorical judgment, probability 0-1, plausible alternative, contradiction expectation and scope boundary.
- Clinical diagnosis is out of scope.

## Primary metrics
- exact agreement;
- exact + partial/directional agreement;
- false-certainty rate;
- contradiction sensitivity;
- Brier score;
- mean calibration gap;
- inter-rater agreement.

## Decision thresholds
### GREEN / GO
- N >= 48;
- inter-rater agreement >= 0.80;
- exact agreement >= 0.75;
- exact + partial >= 0.90;
- false-certainty <= 0.08;
- contradiction sensitivity >= 0.85;
- Brier <= 0.18;
- mean calibration gap <= 0.10;
- zero recurrent critical failures caused by scalar collapse of POWER_VECTOR or TRUST_VECTOR axes.

### AMBER / CONTINUE R&D
No critical RED gate, but more than two metrics remain in intermediate range. Recalibrate before further automation or product claims.

### RED / STOP-REDESIGN
Any critical failure, including:
- inter-rater agreement < 0.67;
- exact agreement < 0.60;
- exact + partial < 0.80;
- false-certainty > 0.15;
- contradiction sensitivity < 0.70;
- Brier > 0.25;
- mean calibration gap > 0.18;
- two or more critical vector axes fail repeatedly, or non-homologous constructs are again collapsed into a scalar.

## Investment rule
The rational next step is to continue only through B5. Do not widen methodological scope or make product-level accuracy claims until B5 is independently adjudicated. If B5 is GREEN, proceed to productization/calibration. If AMBER, continue narrowly in R&D. If RED, stop expansion and redesign or narrow scope.

## Current state
PREREGISTRATION: FROZEN
SCORECARD: READY
DECISION GATE: READY
INDEPENDENT ADJUDICATION: PENDING
FINAL GO/NO-GO: PENDING
