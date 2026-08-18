# SOAiaCore · Radar Analytics Specification

Status: PROPOSED / SOURCE-PERSISTED
Version: 2026-08-17.02
Date: 2026-08-17

## Objective
Provide a quantitative layer beneath symbolic/editorial interpretation so visual salience and psychosocial pattern strength are traceable to measurable signals without reducing analysis to a rigid fact/non-fact binary.

## Unit of analysis
Event: message, image, OCR segment, alert or system observation with event_id, source, actor_ref, timestamp, content_hash, sensitivity_class and approval_state.

Derived analytic units:
- micro_signal: local observation with limited standalone weight;
- signal: structured observation with context;
- pattern: recurrent or convergent signal configuration;
- dynamic: relational/temporal pattern involving actors, themes or roles;
- inference: interpretation supported by one or more patterns;
- profile_hypothesis: provisional longitudinal model.

## Core quantitative metrics
1. Frequency: count(term/entity/signal, window).
2. Recurrence: number of distinct temporal buckets containing the signal.
3. Source diversity: distinct approved sources containing the signal.
4. Co-occurrence: pair frequency within the same event or configured context window.
5. Burst score: current-window frequency relative to historical baseline.
6. Novelty: inverse historical prevalence, capped to avoid one-off noise dominating.
7. Evidence density: number of evidence-linked observations supporting a card.
8. Operator relevance: explicit operator-approved weighting; never inferred from private attributes.
9. Confidence: function of source quality, corroboration, recurrence, convergence, contradictory evidence and data completeness.

## Psychosocial / relational metrics
10. Reciprocity: balance of initiation/response across actors in a defined context.
11. Asymmetry: sustained imbalance in initiation, attention, repair, disclosure or other measurable interaction behavior.
12. Temporal sequence: order of signals/events and repeated transition patterns.
13. Tone shift: material change in linguistic register, affective valence or interaction style relative to actor/context baseline.
14. Contextual omission: absence of an expected action/signal only when a valid baseline and opportunity-to-occur exist.
15. Repair index: recurrence and form of attempts to restore interaction after conflict/disruption.
16. Triangulation/co-alliance: repeated three-or-more actor configurations or indirect relational routing.
17. Theme migration: movement/displacement of a topic across actors or contexts.
18. Cross-signal convergence: number and relative independence of different signal families supporting the same inference.
19. Contradiction load: strength/number of observations inconsistent with the leading inference.
20. Longitudinal stability: persistence of a pattern across time windows.

## Evidence model
The radar uses graded evidence rather than binary admission.

Evidence classes:
- DIRECT: explicit statement/action/documentary observation;
- BEHAVIORAL: interactional behavior observable in the corpus;
- RELATIONAL: reciprocity, asymmetry, sequence or network pattern;
- LINGUISTIC: wording, metaphor, irony, tone or register;
- TEMPORAL: recurrence, latency, sequence, burst or persistence;
- CONTEXTUAL: omission, contrast with baseline, role/context dependency;
- MULTIMODAL: image/OCR/media-derived signal with confidence retained.

These classes are not truth ranks. They describe how support is carried.

## Soft evidence accumulation
A soft signal may receive substantial analytic weight when it shows:
- repeated occurrence;
- convergence with independent signal types;
- consistency across windows/contexts;
- low contradiction load;
- longitudinal stability;
- predictive usefulness on later observations.

A single soft signal normally has low standalone weight. Accumulation can raise inference confidence.

## Competing inference model
Each material inference may maintain:
- leading interpretation;
- alternative interpretation(s);
- supporting signal IDs;
- contradictory signal IDs;
- current confidence;
- future discriminator: observation that would materially change the ranking.

Do not force multiple alternatives when evidence strongly favors one explanation.

## Suggested composite salience
Baseline visual salience remains:
SAL = 0.25*frequency_norm + 0.20*burst_norm + 0.15*recurrence_norm + 0.15*source_diversity_norm + 0.15*cooccurrence_norm + 0.10*novelty_norm.

This is a starting calibration, not a truth score.

## Suggested psychosocial pattern strength
PPS is a provisional calibration target, not production truth:
PPS = 0.20*recurrence + 0.15*cross_signal_convergence + 0.15*longitudinal_stability + 0.10*context_diversity + 0.10*temporal_sequence_strength + 0.10*reciprocity_or_asymmetry_strength + 0.10*tone_or_register_shift + 0.10*(1-contradiction_load).

Weights MUST be calibrated against human expert/operator judgments before production use. PPS can rank patterns; it cannot independently establish clinical diagnosis, hidden intent or moral character.

## Alert levels
L0 INFO: persistent record, no interruption.
L1 NOTICE: visible in tray.
L2 REVIEW: operator review recommended.
L3 HIGH: requires explicit acknowledgement.
L4 CRITICAL: reserved for operational/security conditions with objective triggers; symbolic/interpersonal content cannot reach L4 solely from model interpretation.

A high-confidence psychosocial pattern may be analytically important without becoming an operational L4 alert.

## Historical comparison
Default windows: current 24h / previous 7d / trailing 30d when data volume permits. Longer windows may be used for longitudinal profile hypotheses.

If denominator < minimum sample, label INSUFFICIENT BASELINE rather than extrapolating. Contextual omissions require both baseline and opportunity-to-occur.

## Keyword/entity handling
Keyword matches are signals, not conclusions. Maintain canonical terms + aliases; preserve exact match provenance. Sensitive terms receive stricter retention/logging rules. Personal names should use stable pseudonymous actor_ref in analytics tables where possible.

Names, sexual language, power/status language, drug/alcohol terms, conflict terms and other socially meaningful vocabulary may be retained as signals when relevant; their presence alone does not determine motive or profile.

## Image/OCR handling
Store media hash and derived OCR separately. OCR confidence must be retained. Low-confidence OCR cannot independently trigger high-impact operational alerts, but it may remain as a low-weight signal and gain value if corroborated.

## Fictional/pseudonymous corpora
Fiction, pseudonymization, role-play or anonymization limits claims about external identity. It does not invalidate structural, narrative, conversational, relational or psychosocial pattern analysis inside the corpus.

## FYG/FIG
FYG/FIG is a presentation/tone taxonomy. Each phrase may have one selected tone and optional alternatives. Tone color is UI metadata, not evidence severity.

## Validation
Before production:
- create blinded historical samples;
- compare system ranking with operator/expert ranking;
- measure precision@K and recall-oriented metrics where relevant;
- measure false-positive and false-negative rates;
- compare confidence calibration against adjudicated judgments;
- inspect pattern stability over time;
- evaluate competing-inference resolution;
- inspect drift by source and time window;
- record calibration version.

For psychosocial analysis, validation must not reward only literal facts. Human adjudication should score whether the inference is reasonable given the total signal field and whether uncertainty was represented appropriately.

## Privacy
No sensitive raw payload in telemetry dashboards. Aggregate where possible. Retention and deletion policy must be explicit before backup is enabled.

## Governing principle
FLEXIBLE DISCOVERY, TRACEABLE ASSERTION.

The radar should be sensitive enough to discover weak and cumulative social signals, while every high-impact inference remains linked to its supporting and contradictory evidence.