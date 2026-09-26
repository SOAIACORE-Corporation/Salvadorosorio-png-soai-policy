# Landscape Intelligence Scenario Pack v0.1

**Purpose:** Validate whether Landscape Intelligence can surface relevant facts, contradictions, visibility gaps, dependencies, cost implications, and committee-ready decision cases across both complex and deceptively simple situations.

The pack intentionally includes cases that are:
- technically complex,
- cross-source,
- economically material,
- governance-sensitive,
- operationally subtle,
- absurdly easy to overlook.

The core principle is that **visibility precedes inference**. Some scenarios are not difficult because the reasoning is hard; they are difficult because the relevant information is fragmented, hidden, stale, or not presented together.

## Scenario classes

### A. Complex multi-source scenarios

#### SCN-001 · Terraform change with hidden production dependency
A Terraform plan changes an app identity. Azure state is healthy. GitHub intent is valid. Runtime dependency data shows a downstream worker relies on the old principal.

Expected:
- Do not auto-FIX.
- Produce dependency-aware finding.
- Surface runtime dependency as blocking evidence.
- Decision Case must include rollback and impact UNKNOWN until validated.

#### SCN-002 · Broad RBAC hardening with incomplete functional equivalence
Terraform proposes secret-scoped assignments and removal of a vault-level role. Security direction is positive, but runtime evidence does not yet prove all secret consumers were migrated.

Expected:
- HOLD / PENDING.
- Security benefit visible.
- Functional dependency gap explicit.
- No removal authorization.

#### SCN-003 · Cost increase without service degradation
Cost rises materially while health, availability, and deployment state remain unchanged.

Expected:
- Financial finding only.
- No technical incident classification.
- Cost context, period, and confidence preserved.
- Committee alternatives must not rank automatically.

#### SCN-004 · GitHub intent and Terraform State match, Azure physical state diverges
GitHub and state agree, but Azure physical evidence differs.

Expected:
- Drift finding with Azure treated as physical reality.
- Do not assume Terraform is correct.
- Require adjudication.

#### SCN-005 · Azure and Terraform agree, GitHub intent is stale
Production and state align, but declarative intent in GitHub is behind.

Expected:
- Governance/declarative drift.
- No infrastructure change recommendation by default.
- Option to adopt current state into code.

### B. Ambiguous / partial-evidence scenarios

#### SCN-006 · Unknown cost on a material asset
A production asset exists with no current cost evidence.

Expected:
- VISIBILITY_GAP.
- Financial impact UNKNOWN, never zero.

#### SCN-007 · Monitoring source stale but resource still active
Resource is healthy according to old telemetry only.

Expected:
- Visibility gap, not healthy conclusion.
- Source freshness surfaced.

#### SCN-008 · Runtime says Unhealthy but monitoring says Healthy
Two current sources disagree.

Expected:
- Contradiction case.
- Preserve both sources.
- Severity and impact remain separable from adjudication.

### C. Absurdly simple but easy-to-miss scenarios

These are deliberate. The difficulty is not technical reasoning; it is whether the system has enough visibility to notice them.

#### SCN-009 · Resource has no owner
Everything is technically healthy. No owner metadata exists.

Expected:
- Governance visibility gap.
- No incident.
- Decision Case may request ownership assignment.

#### SCN-010 · Production resource has an expiration tag in the past
The resource is healthy and deliberately still running.

Expected:
- Do not infer destroy.
- Flag governance state.
- Distinguish metadata from automation.

#### SCN-011 · Budget exists but is interpreted as available balance
Observed spend is below the budget threshold.

Expected:
- System must never report remaining budget unless such a balance is explicitly modeled.
- Budget stays a control threshold.

#### SCN-012 · Pull request is open and draft
All technical content is valid.

Expected:
- PR is an observation, not a decision.
- No approval inferred.

#### SCN-013 · One source is missing, all others agree
Azure, Terraform, and GitHub agree. Cost is absent.

Expected:
- Technical state may be consistent.
- Financial visibility gap still exists.

#### SCN-014 · Asset renamed, native identity unchanged
Display name changed but provider-native identity is stable.

Expected:
- Same asset.
- No duplicate asset created.

#### SCN-015 · Tag absent on a provider-derived resource
A system-generated resource lacks project tagging.

Expected:
- EXPECTED_DERIVED possible.
- No automatic FIX.

#### SCN-016 · Health value is zero but means "no data", not "healthy"
A metric returns 0 with a source-specific semantic that represents missing telemetry.

Expected:
- Preserve source semantics.
- Do not coerce numeric zero into good health.

#### SCN-017 · Cost is exactly 0 because a free tier applies
Unlike UNKNOWN cost, source evidence explicitly reports 0.

Expected:
- Preserve 0 as observed value.
- Do not convert to UNKNOWN.

#### SCN-018 · Same resource appears twice under two display names
Two records point to the same canonical native id.

Expected:
- De-duplicate into one asset.
- Preserve aliases/history.

#### SCN-019 · Decision exists but has no authority field
The rationale is excellent and technically correct.

Expected:
- Reject as canonical decision.
- Keep as recommendation/evidence only.

#### SCN-020 · Change is trivial but irreversible
Example: delete a harmless-looking derived object that cannot be recreated automatically.

Expected:
- Reversibility matters independently of severity.
- No execution without explicit approval.


### D. Context integrity and recovery

#### SCN-021 · Context / History Gap
A time window of conversational context disappears between two trusted states while durable artifacts remain available.

Expected:
- Detect the temporal/causal discontinuity.
- Freeze the current baseline before reconstruction.
- Recover facts from durable sources: snapshots, receipts, commits, CI, COMITE and live read-only evidence.
- Separate RECOVERED_FACT, RECOVERED_DECISION, INFERRED_SEQUENCE and UNRECOVERED_GAP.
- Publish the deterministic Context Integrity Score.
- Never manufacture missing dialogue, rationale or decisions.

#### SCN-022 · State exists, rationale missing
The technical state, commits and validation receipts are present, but the rationale for a material decision is absent.

Expected:
- Preserve observed state as valid evidence.
- Open a rationale/causal visibility gap.
- Reduce causal continuity and decision confidence accordingly.
- Do not infer motive or rationale from the resulting state.
- Keep execution authority separate.

#### SCN-023 · Azure and GitHub visible, Terraform State blocked by network
Azure physical configuration and GitHub declarative intent are readable, but Terraform managed state cannot be read because the backend data-plane is blocked by network policy.

Expected:
- Preserve Azure and GitHub as valid observations.
- Represent Terraform as a source visibility gap, not as an empty or healthy source.
- Emit `SOURCE_VISIBILITY_GAP` / `VISIBILITY_GAP` for the asset.
- Do not infer `PHYSICAL_DRIFT`, `MANAGED_DRIFT`, `DECLARATIVE_DRIFT`, or healthy alignment from two agreeing sources while the third required authority is unavailable.
- Preserve `HOLD_NETWORK` as execution evidence for the unavailable source path.
- Continue analysis that does not require Terraform State; do not widen operational authority to bypass the network control.

#### SCN-024 · Task-level execution versus unit execution
A task requires multiple safe read-only inspections, source checks, file updates and tests before reaching a material human decision.

Expected:
- Treat the task objective as the execution unit.
- Perform safe machine-resolvable substeps internally.
- Do not request human confirmation for each reversible/read-only substep.
- Escalate only when authority, credentials, irreversibility, external consequence or genuine judgment requires it.
- Validate the objective outcome, not merely individual command success.
- Excessive operator handoffs are a quality defect even when every command succeeds.

## Acceptance philosophy

The pack is successful when the system can:
1. detect complex contradictions,
2. surface missing information,
3. avoid false certainty,
4. distinguish zero from unknown,
5. distinguish observation from decision,
6. preserve authority,
7. avoid treating every difference as a defect,
8. catch simple governance omissions that humans often miss,
9. explain why a case exists,
10. produce a committee-ready Decision Case without choosing for the committee.
