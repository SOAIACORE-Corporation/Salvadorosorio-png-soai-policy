# SOAiaCore · Flexible Psychosocial Inference Standard

Status: PROPOSED / SOURCE-PERSISTED
Version: 2026-08-18.03
Date: 2026-08-18
Applies to: conversational analysis, social analysis, behavioral patterning, relational dynamics, symbolic/radar interpretation, fictional or pseudonymous corpora.

## 1. Principle
SOAiaCore uses **ANALYTIC FLEXIBILITY WITH TRACEABILITY**.

The system must be permissive in discovery and disciplined in assertion. Epistemic labels describe distance from direct observation; they do not determine whether information is analytically admissible.

## 2. Canonical inference chain
OBSERVATION → MICRO-SIGNAL → SIGNAL → PATTERN → DYNAMIC → INFERENCE → PROFILE HYPOTHESIS → CONTRAST → REVISION.

Any stage may be retained when useful. A downstream inference must preserve links to upstream support.

## 3. Admissible signal families
DIRECT, BEHAVIORAL, RELATIONAL, LINGUISTIC, TEMPORAL, CONTEXTUAL and MULTIMODAL signals are admissible.

Examples include recurrence, contradiction, irony, metaphor, shifts in register, initiative, reciprocity, asymmetry, sequence, silence/omission with baseline, conflict repair, alliances, triangulation, topic displacement, co-occurrence, affective/sexual/status/power language, longitudinal change, group dynamics and OCR/media-derived cues.

## 4. Soft evidence rule
Soft evidence is not discarded merely because it is indirect. Its weight may increase through:
- recurrence;
- cross-signal convergence;
- contextual diversity;
- longitudinal stability;
- relative independence of signals;
- low contradiction load;
- predictive usefulness.

A single weak cue should normally remain low-weight. Convergent cues may support a strong inference.

## 5. Competing inference rule
When ambiguity is material, preserve:
- leading inference;
- plausible alternative(s);
- evidence supporting each;
- contradictory evidence;
- current confidence;
- future discriminator.

Do not manufacture alternatives for artificial balance.

## 6. Confidence
Confidence refers to the strength of the interpretation given the available corpus, not metaphysical certainty.

Suggested bands:
- LOW: exploratory; insufficient convergence or substantial contradiction;
- MEDIUM: meaningful pattern; some convergence, but alternatives remain material;
- HIGH: repeated/convergent/stable pattern with limited contradiction inside the corpus.

High confidence does not transform a psychosocial inference into a clinical diagnosis or proven hidden intent.

## 7. Profiles
Profiles are provisional models. They may describe interaction style, reciprocity, status dynamics, conflict behavior, observable regulation patterns, affiliation/avoidance, narrative power and other corpus-grounded constructs.

They are revisable and should update when superior evidence arrives.

## 8. Fictional, pseudonymous and reconstructed corpora
Pseudonyms, fictional persons, role-play, synthetic cases, anonymization and time-shifted reconstruction do not invalidate internal analysis.

They do limit external identity claims. The system analyzes the corpus universe unless external identity has been independently established.

## 9. Non-discard / non-certification rule
**Do not discard because indirect. Do not certify because persuasive.**

Preserve → weight → connect → contrast → revise.

## 10. Radar implications
The radar may model both **salience** and **pattern strength**.

Salience answers: what is prominent or changing?
Pattern strength answers: how coherent, recurrent, convergent and stable is the inferred social/behavioral configuration?

Neither is a truth score.

## 11. Safety and clinical boundary
The flexible standard does not authorize unsupported diagnosis, defamatory certainty, autonomous publication or autonomous outbound action.

Clinical/psychiatric labels require a materially higher evidentiary standard than ordinary psychosocial pattern analysis.

## 12. Validation
Validation must include cases where the correct expert judgment depends on accumulated context rather than literal statements. A system that only identifies explicit facts fails this standard even if its factual precision is high.

Evaluation should therefore measure:
- pattern recall;
- inference reasonableness;
- confidence calibration;
- sensitivity to contradiction;
- alternative-hypothesis handling;
- longitudinal stability;
- operator/expert acceptance;
- false certainty rate.

## 13. Governance
This standard is additive. It does not alter DecisionOS v0.3-SHADOW-FROZEN, SOA_CONTEXT routing, change locks, PRECHECK or outbound approval gates.

## 14. Multi-layer inference rule · RADAR-CAL-01 B2
B2 demonstrated that flexibility alone is insufficient when the claim lives at a different analytical scale. The engine must select evidence layers according to the type of claim.

Canonical multi-layer route:

MICROSEQUENCE → LONGITUDINAL PATTERN → NETWORK / TOPOLOGY → ROLE CONTEXT → INFERENCE → CONTRADICTION → CONFIDENCE → REVISION.

Rules:
- Local pragmatic claims prioritize complete microsequences.
- Pattern claims require recurrence across time.
- Structural claims such as brokerage, centrality, cross-block participation or durable coalition require network/topological evidence and must not be inferred from isolated windows alone.
- Network position does not prove conscious mediation, private alliance, affect, intent or psychological dependence.
- Distinguish EPISODIC COALITION from STABLE COALITION.
- Distinguish CONSCIOUS MEDIATION from STRUCTURAL BROKERAGE.
- Caution that prevents over-generalization is not automatically an analytical error.

### B2 empirical signal
On 9 comparable F5 structures with predictions frozen before opening the human validation sheet:
- rigid exact categorical match: 4/9 (44.4%);
- flexible exact categorical match: 5/9 (55.6%);
- rigid mean ordinal distance: 0.333;
- flexible mean ordinal distance: 0.222;
- within one ordinal step: rigid 8/9; flexible 9/9.

The principal flexible failure was under-detection of structural brokerage when only local conversational windows were used. Post-hoc inspection of F5 Centrality showed SOA with betweenness 0.46667, degree 16 and cross-block participation 0.607, explaining why structural adjudication can be correct even when no single window displays an overt mediating act.

These results are retrospective and corpus-specific; they are validation signals, not generalizable population estimates.

## 15. Multi-axial inference and non-comparability rule · RADAR-CAL-01 B3
B3 adds a second constraint: selecting the correct analytical scale is necessary but not sufficient when the target construct itself contains different species of capacity.

For social/institutional power, the minimum representation is:

POWER_VECTOR = [interpretive_influence, operational_authority, network_brokerage, relational_salience, symbolic_prominence]

### 15.1 Non-comparability rule
Before ranking or comparing actors, the engine must determine whether the compared variables are semantically homologous. If they are not, it must return a vector/profile rather than collapse them into a single ordinal score.

Mandatory distinctions:
- INFLUENCE ≠ AUTHORITY.
- CENTRALITY ≠ SOVEREIGNTY.
- STRUCTURAL BROKERAGE ≠ CONSCIOUS MEDIATION.
- RELATIONAL SALIENCE ≠ CONTROL.
- SYMBOLIC PROMINENCE ≠ OPERATIONAL CAPACITY.

Correlations among these dimensions may be analytically useful but do not establish equivalence.

### 15.2 Component-level traceability
Each vector component must preserve its own:
- source signals;
- analytical scale;
- competing inference(s);
- contradiction load;
- confidence;
- scope boundary.

A total power score is prohibited by default unless a specific use case defines and validates a commensurable aggregation function.

### 15.3 B3 validation signal
Ten predictions were frozen after integrating microsequence, longitudinal, network/topological and role-context evidence, before opening the POST-SEM reference. Six claims were directly comparable with POST-SEM and aligned semantically in 6/6 cases; four additional checks were supported by the audit matrix.

Important limitation: B3 is **not a blind benchmark** because the evaluator had already been exposed in-session to the `Comparacion espejo` sheet. It is a prospective-format consistency test. The result supports architectural coherence, not external generalization.

The principal B3 conclusion is that the SOA↔Abdiel dyad is better represented as complementary-asymmetric across different power species: interpretive/narrative influence and operational sovereignty are not a single continuum.

### 15.4 Next validation gate
B4 must use a HOLDOUT corpus not previously inspected by the evaluator/model, freeze multi-layer and multi-axial predictions before adjudication, and score false certainty, contradiction handling, calibration and inter-rater agreement.