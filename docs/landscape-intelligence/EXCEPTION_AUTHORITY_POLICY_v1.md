# SOAiaCore Exception Authority Policy v1

## Canonical authority

All exceptions to active controls, policies, gates, HOLDs, materiality rules,
execution boundaries, regulatory gates, security constraints, or other governed
system restrictions require explicit authority from:

**SOA / Salvador Osorio Ayala**

## Scope

This rule applies to exception handling only.

Normal decisions remain with their defined owner, committee, architecture,
security, finance, operations, regulatory, or other authorized domain owner.

An exception is any request to bypass, override, suspend, waive, or proceed
outside an active control or required condition.

## Required exception record

Every exception must preserve:

- exception_id
- requested_control
- reason
- authority = Salvador Osorio Ayala
- evidence_refs
- scope
- effective_from
- effective_to or review trigger
- residual_risk
- reversibility
- validation requirement
- receipt

## Governing rule

A system component may identify that an exception could be useful.
It may model the consequences of granting or rejecting it.
It may not grant the exception.

Only the canonical exception authority may authorize it.

## Fail-closed semantics

If authority is missing, ambiguous, delegated without explicit canonical
approval, or different from SOA / Salvador Osorio Ayala:

`EXCEPTION_REJECTED`

The underlying control remains in force.

## Separation of powers

- AI: analyze, simulate, recommend.
- Domain owner: decide within normal policy boundaries.
- SOA / Salvador Osorio Ayala: exclusive exception authority.
- Executor: execute only after applicable decision and exception gates pass.
