# SOAiaCore Memory Integrity Cycle v0.1

**Status:** PILOT / READ-ONLY / TESTABLE  
**Method:** SOAiaCore / MOCATRIZ adaptive execution

## Purpose

Turn memory continuity into a repeatable objective without turning the method into bureaucracy.

The cycle is deliberately compact:

```text
OBSERVE → UNDERSTAND → RESOLVE → DEMONSTRATE
```

The phases are reasoning minima, not mandatory micro-steps. A simple case may pass through them almost instantly; a material case may expand internally.

## OBSERVE

Establish what evidence exists and what is missing.

Output:
- required requirements;
- confirmed requirements;
- unresolved requirement IDs;
- completion percentage.

## UNDERSTAND

Use the existing Context Integrity model to determine evidentiary continuity.

No second competing "memory confidence" score is introduced in v0.1.

Critical gates remain:
- `MISSING_REQUIRED_AUTHORITY`
- `MISSING_MATERIAL_PRIMARY_EVIDENCE`

Missing verbatim dialogue is disclosed but is not automatically equivalent to lost state.

## RESOLVE

Classify canonicalization:

- `ELIGIBLE`: no unresolved required evidence.
- `PARTIAL`: unresolved requirements exist but no critical gate is open.
- `BLOCKED`: a critical authority or material-primary-evidence gate is open.

The pilot is read-only. It may identify recovery/adjudication actions but does not mutate durable source systems automatically.

## DEMONSTRATE

Publish four kinds of evidence:

### Context Integrity
The existing deterministic continuity score and gates.

### Human Interaction Efficiency

```text
necessary_human_actions / total_human_actions
```

and:

```text
avoidable_human_actions / total_human_actions
```

When no human action is needed, efficiency is 100% and avoidable rate is 0%.

### Recovery Efficiency

Measures recoverable execution errors resolved without human intervention:

```text
autonomously_resolved_recoverable_events / recoverable_events
```

Non-recoverable authority events are excluded from this denominator.

### Methodology efficiency

`Control Yield` measures controls that materially changed the outcome:

```text
useful_controls / executed_controls
```

`Methodological Overhead` measures executed controls that added no decision value:

```text
non_value_adding_controls / executed_controls
```

For a non-empty control set:

```text
Control Yield + Methodological Overhead = 100%
```

This corrects the earlier semantic inversion in which a useful-control ratio had been named "overhead."

## Adaptive execution rule

Recoverable friction is not a showstopper.

The cycle continues through:
- naming/path misses;
- redundant controls;
- recoverable implementation defects;
- non-material source gaps;
- alternative implementations.

Canonicalization stops when evidence or authority is materially insufficient.

## Authority boundary

The cycle does not grant:
- merge authority;
- infrastructure mutation authority;
- exception authority;
- production deployment authority;
- permission to reinterpret external obligations.

## Success criterion

The pilot succeeds when it can produce one integrated answer to:

1. What do we know?
2. What remains unresolved?
3. Is the memory state eligible to become canonical?
4. How much human intervention was actually necessary?
5. How much of the methodology produced useful signal rather than overhead?
6. Can the result be reproduced from durable evidence?
