# SOAiaCore · RADAR-CAL-01 B5 · Adjudication Package

Status: READY FOR RATER NOMINATION
Date: 2026-08-18
Branch: `soaia/as-is-hardening-2026-08-17`

## Purpose
Prepare the independent-adjudication gate for RADAR-CAL-01 B5. B5 is a decision gate, not a confirmation exercise.

## Required package
Each adjudicator receives only:
1. invitation/engagement note;
2. B5 independent adjudication manual;
3. privacy/confidentiality notice;
4. blinded corpus units;
5. individual scoring sheet;
6. minimal construct glossary when required.

They must not receive model probabilities, B1-B4 outcomes, previous adjudications, rankings, PRE/GOLD tables, or the other rater's responses.

## Core rules
- Minimum 48 evaluable units.
- Two independent raters.
- Stable UNIT_ID across PRE, blinded package and GOLD.
- Different randomized presentation order per rater.
- Pseudonymization by default.
- No clinical diagnosis targets.
- No unit replacement after freeze without explicit versioning.
- First-round agreement must be computed before joint reconciliation.

## Scored fields
Construct; class/direction; confidence 0-1; supporting evidence; contradictory evidence; plausible alternative; contradiction status; scope boundary; ambiguity; optional notes.

## Decision metrics
Inter-rater agreement; exact agreement; exact+partial; false-certainty rate; contradiction sensitivity; Brier score; mean calibration gap; critical-axis error rate.

## Critical semantic constraints
- STRUCTURAL TRUST != OPERATIONAL TRUST.
- TRAFFIC != TRUST.
- CENTRALITY != AUTHORITY.
- PERSISTENCE != INTIMACY.
- TOTAL RECIPROCITY != POSITIVE RECIPROCITY.
- NARRATIVE POWER != OPERATIONAL POWER.

## Gate
GREEN only if the preregistered B5 thresholds are met and no recurrent critical construct-collapse is detected. AMBER allows constrained R&D only. RED requires stop/redesign before further product complexity.

## Current operational state
Methodology, scoring register, rater manual, privacy notice, email templates and blinded-corpus assembly protocol are prepared. Pending: nomination of two eligible raters, generation/freeze of the 48+ unit blinded corpus, controlled sharing, completion of both independent rounds, scoring and final GO/AMBER/RED decision.
