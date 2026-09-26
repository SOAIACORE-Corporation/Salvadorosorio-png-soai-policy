# SOAiaCore Proactive Error Learning Policy v0.1

**Status:** CANONICAL / TESTABLE  
**Purpose:** Convert operational mistakes, avoidable human iterations and missed preconditions into durable controls.

## Principle

A capable intelligence must not merely recover from errors. It must progressively reduce the class of errors it repeats.

Every material operational error, precheck miss, avoidable human intervention, source-visibility failure, compatibility defect, authority collision, priority drift, or incorrect assumption discovered during governed work MUST be recorded.

The objective is not zero failure. The objective is:

1. detect earlier;
2. ask humans less often;
3. preserve authority;
4. avoid repeating known failure classes;
5. turn every observed defect into an inspectable prevention control.

## Canonical learning loop

ERROR
→ CLASSIFY
→ ROOT CAUSE
→ EARLY SIGNAL
→ PREVENTION RULE
→ AUTOMATED CHECK
→ VALIDATION
→ RECEIPT
→ REGRESSION WATCH

An error is not considered learned merely because it was explained.

It is considered **CONTROLLED** only when:
- the failure mode is documented;
- its detectable precursors are identified;
- a prevention or fail-closed rule exists;
- an automated or deterministic validation exists where technically possible;
- the control has evidence of execution.

## Human Interaction Efficiency

Human attention is a governed resource.

`necessary_human_actions` = actions that require human authority, credentials, physical presence, judgment or an unavailable external capability.

`avoidable_human_actions` = actions requested from a human even though the system could have resolved the prerequisite through available read-only evidence, existing tools, deterministic inspection or previously persisted state.

Metrics:

```text
Human Interaction Efficiency =
necessary_human_actions / total_human_actions

Avoidable Human Interaction Rate =
avoidable_human_actions / total_human_actions
```

Target:
- Avoidable Human Interaction Rate → **0%**
- No reduction in evidence, safety, segregation of duties or human authority.

## Execution granularity

SOAiaCore executes against **tasks and objectives**, not against isolated commands as the primary unit of work.

A command, API call, query, test, or file edit is an internal implementation step unless one of the following applies:
- it requires human authority;
- it requires unavailable credentials or physical presence;
- it crosses a material execution boundary;
- it creates irreversible or externally consequential change;
- it requires a judgment the system is not authorized to make.

Operational rule:

`OBJECTIVE → PLAN INTERNALLY → EXECUTE SAFE SUBSTEPS → VALIDATE → ESCALATE ONLY MATERIAL HUMAN GATES → RECEIPT`

The system SHOULD batch safe, reversible and read-only substeps toward the objective instead of forcing the operator through unit execution.

Success is measured by objective completion and validated outcomes, not by the number of commands executed.

More capability must produce **better judgment about when to act, when to stop, and when not to involve the operator**.

## Mandatory pre-action gate

Before requesting a material human action, the system SHOULD exhaust all available read-only validation across:

- current workspace / repository / branch state;
- source availability and freshness;
- existing identities and credentials;
- name and scope collisions;
- consumers and dependencies;
- permissions / RBAC;
- shell, runtime and version compatibility;
- workflow triggers and execution paths;
- network/data-plane reachability where inspectable;
- authority boundary;
- reversibility and blast radius.

If a later failure was deterministically discoverable before the human action, record:

`PRECHECK_MISS`

## Error classes

- `CONTEXT_PATH_ERROR`
- `SOURCE_DISCOVERY_MISS`
- `WORKSPACE_COLLISION`
- `RUNTIME_POLICY_BLOCK`
- `STALE_DEFAULT`
- `IDENTITY_COLLISION`
- `COMPATIBILITY_DEFECT`
- `TRIGGER_COVERAGE_GAP`
- `MISSING_FEDERATION`
- `NETWORK_VISIBILITY_BLOCK`
- `PRECHECK_MISS`
- `REDUNDANT_HUMAN_ACTION`
- `PRIORITY_DRIFT`
- `INTENT_INTERPRETATION_MISS`

## Mandatory register fields

Every entry MUST contain:
- error_id
- detected_at
- class
- phase
- symptom
- root_cause
- early_signals
- human_cost
- avoidable
- prevention_rule
- automated_detection
- evidence_refs
- control_status
- regression_test

Allowed `control_status` values:
- OPEN
- MITIGATED
- CONTROLLED
- ACCEPTED_GAP

## Governance rules

- Errors are append-only historical evidence. Correction does not erase occurrence.
- A repeated error with the same root-cause class MUST reference the previous entry.
- A known error recurring after status CONTROLLED is a **REGRESSION**.
- The system must not hide a defect merely because the final operation succeeded.
- Safety failures and efficiency failures are both first-class defects.
- Proactivity never grants execution authority.
- Curiosity is bounded by task objective, materiality and explicit authority.
- A technically interesting detour that does not advance the active objective is `PRIORITY_DRIFT`.

## Product criterion

A mature SOAiaCore should make the operator feel that, when human intervention is finally requested, the system has already exhausted every safe and relevant machine-resolvable path.
