# MOCATRIZ · Modelo Adaptativo de Ejecución Autónoma, Recuperación e Interacción Humana v1

**Status:** CANONICAL / TESTABLE  
**Unit of execution:** Objective, not command.

## Fundamental cycle

```text
OBSERVE → UNDERSTAND → RESOLVE → DEMONSTRATE
```

The phases are adaptive reasoning states, not a rigid workflow. The agent may move forward, return, repeat, abandon a strategy or adopt another when evidence justifies it.

The invariant is:

> trazabilidad + contexto + dirección hacia el objetivo

## Operational principles

- Results of actions become new evidence.
- Expected and unexpected results are both evidence.
- Changing strategy in response to new evidence is correct behavior.
- Recoverable errors do not stop the objective automatically.
- Human intervention is a normal execution state, not automatically a failure.
- A human request stops only the affected execution branch.
- Human responses are incorporated as evidence and may cause re-entry through UNDERSTAND.
- SHOWSTOPPER is an operational conclusion reached after reasonable recovery attempts, not a prescriptive list.
- Completion requires evidence against the original acceptance criteria.
- Finishing actions is not equivalent to finishing the objective.

## Human Task

A human task must persist:
- Objective ID
- Execution ID
- Human Task ID
- Correlation ID
- reason
- minimum decision context
- question
- evidence
- resume point

Canonical state:

`WAITING_HUMAN`

A response may resume only the execution that matches all correlation identifiers.

## Closure states

- COMPLETED
- COMPLETED_WITH_EXCEPTIONS
- MITIGATED
- PENDING
- WAITING_HUMAN
- BLOCKED
- SHOWSTOPPER

## Telemetry

MOCATRIZ measures:
- Objective Completion
- Autonomous Completion
- Recovery Efficiency
- Strategy Mutation
- Human Dependency
- Human Intervention Efficiency
- Resume Success
- Correlation Integrity
- Self-Regulation decisions
- False Completion
- Drift
- Control Yield
- Methodological Overhead

### False Completion

A completion claim is false when material applicable acceptance criteria remain unresolved.

### Drift

Drift exists when execution increasingly departs from the objective without producing evidence that materially advances resolution.

### Methodological Overhead

Controls that repeatedly neither change a decision, reduce uncertainty nor produce closure evidence are candidates for simplification or removal.

## Execution receipt

A reconstructable execution should preserve, at minimum:

```text
objective
execution
observations
hypotheses
decisions
actions
results
failures
recoveries
strategy_changes
human_interactions
contradictions
unresolved_items
final_validation
final_status
methodology_metrics
```

The receipt should reconstruct:

> qué sabía → qué interpretó → qué decidió → qué ocurrió → cómo reaccionó → por qué terminó

## GO MOCATRIZ

Given an objective, context, memory, tools and evidence:

1. advance autonomously;
2. treat results as evidence;
3. recover reasonable errors before escalating;
4. change strategy when evidence warrants it;
5. persist and correlate human tasks when needed;
6. declare SHOWSTOPPER only after reasonable alternatives fail;
7. validate closure against the original objective;
8. preserve enough evidence to reconstruct the execution later.

## Canonical formulation

> No le digas a la autonomía exactamente cómo comportarse y después concluyas que fue autónoma. Dale un objetivo, contexto, memoria, herramientas y retroalimentación sobre sus propias acciones; observa cómo decide, cómo falla, cómo se recupera, cuándo pide ayuda y, sobre todo, cómo determina que realmente terminó.
