# SOAiaCore · Radar Analytics Specification

Status: PROPOSED / SOURCE-PERSISTED
Date: 2026-08-17

## Objective
Provide a quantitative layer beneath symbolic/editorial interpretation so visual salience is traceable to measurable signals.

## Unit of analysis
Event: message, image, OCR segment, alert or system observation with event_id, source, actor_ref, timestamp, content_hash, sensitivity_class and approval_state.

## Core metrics
1. Frequency: count(term/entity, window).
2. Recurrence: number of distinct temporal buckets containing the signal.
3. Source diversity: distinct approved sources containing the signal.
4. Co-occurrence: pair frequency within the same event or configured context window.
5. Burst score: current-window frequency relative to historical baseline.
6. Novelty: inverse historical prevalence, capped to avoid one-off noise dominating.
7. Evidence density: number of evidence-linked observations supporting a card.
8. Operator relevance: explicit operator-approved weighting; never inferred from private attributes.
9. Confidence: function of source quality, corroboration and data completeness.

## Suggested composite salience
SAL = 0.25*frequency_norm + 0.20*burst_norm + 0.15*recurrence_norm + 0.15*source_diversity_norm + 0.15*cooccurrence_norm + 0.10*novelty_norm.

This is a starting calibration, not a truth score. Weights must be benchmarked against operator judgments before production use.

## Alert levels
L0 INFO: persistent record, no interruption.
L1 NOTICE: visible in tray.
L2 REVIEW: operator review recommended.
L3 HIGH: requires explicit acknowledgement.
L4 CRITICAL: reserved for operational/security conditions with objective triggers; symbolic/interpersonal content cannot reach L4 solely from model interpretation.

## Historical comparison
Default windows: current 24h / previous 7d / trailing 30d when data volume permits. If denominator < minimum sample, label INSUFFICIENT BASELINE rather than extrapolating.

## Keyword/entity handling
Keyword matches are signals, not conclusions. Maintain canonical terms + aliases; preserve exact match provenance. Sensitive terms receive stricter retention/logging rules. Personal names should use stable pseudonymous actor_ref in analytics tables where possible.

## Image/OCR handling
Store media hash and derived OCR separately. OCR confidence must be retained. Low-confidence OCR cannot independently trigger high-impact alerts.

## FYG/FIG
FYG/FIG is a presentation/tone taxonomy. Each phrase may have one selected tone and optional alternatives. Tone color is UI metadata, not evidence severity.

## Validation
Before production:
- create a blinded sample;
- compare system ranking with operator ranking;
- measure precision@K, false-positive rate and alert acceptance rate;
- inspect drift by source and time window;
- record calibration version.

## Privacy
No sensitive raw payload in telemetry dashboards. Aggregate where possible. Retention and deletion policy must be explicit before backup is enabled.