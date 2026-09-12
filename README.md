# SOAiaCore — Policy, Runtime & Evidence Architecture

SOAiaCore is a policy-driven technical program for preserving continuity between evidence, memory, interpretation, and decision.

Its governing premise is:

> The signal can travel; authority stays human.

This repository is the public canonical surface for the SOAiaCore policy, runtime, persistence, infrastructure, validation, and evidence model. It is designed to make technical claims inspectable rather than merely persuasive.

## What this repository contains

SOAiaCore brings together:

- evidence and claim contracts with provenance and contradiction handling;
- project-scoped context construction and memory admission boundaries;
- bitemporal persistence for canonical memory, episodic memory, operational state, and DecisionOS;
- a provider-neutral cognitive loop that classifies facts, context, inferences, hypotheses, and working assumptions;
- safety governance for effects classified R0, R1, R2, and R3;
- Python runtime packages, FastAPI services, worker jobs, OCI containers, PostgreSQL migrations, and Terraform infrastructure;
- Azure private-connectivity patterns for the A2 development persistence substrate;
- deterministic tests, golden safety cases, static gates, workflow controls, and execution receipts.

The repository is intentionally a working technical system and governance record. It does not present every implemented component as production-ready.

## Architectural distinction

The system preserves the distinction between:

1. evidence;
2. interpretation;
3. persistence;
4. canonical admission;
5. authorization;
6. material execution.

Thinking is not the same as asserting a fact. Persisting a proposal is not the same as canonizing it. A plan is not an apply. A successful CI run is not proof of a live cloud deployment.

The operating protocol is:

CONTEXT → SYNC → PRECHECK → EXECUTE / CHANGE → VALIDATE → RECEIPT

The decision-evidence flow is:

EVIDENCE → CONTRADICTION → ADJUDICATION → RECEIPT

## Current evidence posture

The public implementation should be read through the following evidence states:

| State | Meaning |
| --- | --- |
| VERIFIED | Supported by visible code and reproducible validation evidence. |
| SPECIFIED | Formally documented, but not yet established as live runtime behavior. |
| CONDITIONAL | Implemented or provisioned, but dependent on a remaining authority, operational, or recovery gate. |
| EXPERIMENTAL | Active branch, prototype, evaluation path, or bounded test vehicle. |
| VISION | Research direction or longer-term system objective. |

### Current status

- R0 policy and safety controls are implemented across runtime code, contracts, tests, static validation, and CI.
- The A2 PostgreSQL DEV substrate has been provisioned in an isolated Azure resource group with public PostgreSQL networking disabled.
- The A2 bitemporal persistence overlay, lineage model, DecisionOS transitions, and private migration design are present in the canonical repository.
- A2 live database migration remains a separately governed material action. The vector extension is allowlisted in the DEV configuration but is not represented as installed in the database by the current public evidence.
- The G3 provider boundary, single-shot harness, pre-Holdout runner, and governed internal batch path are integrated as controlled execution vehicles.
- R1 validation for the provider path uses mocks or bounded no-outbound validation. A real external provider call requires a new exact R2 authority and a same-session precheck.
- Production release is not claimed by this repository. The latest public hardening receipt records material progress with production authorization still blocked.

## R0–R3 effect model

R0–R3 are effect and authorization classes, not product editions.

| Class | Operational meaning |
| --- | --- |
| R0 | Static, deterministic, local, or no-material-effect validation. |
| R1 | Reversible implementation, documentation, test, or branch-scoped change. |
| R2 | Material change or live external execution requiring an exact approved scope. |
| R3 | Destructive, privileged, irreversible, or high-impact action requiring explicit human authorization. |

The fail-closed rule is intentional: the existence of an executor, workflow, or credential path does not itself authorize execution.

## Repository map

| Area | Purpose |
| --- | --- |
| apps | Core, web, and worker application surfaces. |
| packages/python-runtime | Runtime contracts, safety governance, cognitive loop, provider boundaries, and evaluation code. |
| db | Baseline and isolated A2 migration layers. |
| infra/azure | Azure P0 and SOA Intelligence A2 infrastructure definitions. |
| contracts and schemas | Versioned interfaces, invocation/output contracts, claims, context, and review policy. |
| tests and validation | Acceptance, contract, static, integrity, and production-hardening gates. |
| .github/workflows | Static validation, OCI publication, safety gates, runtime smoke tests, and governed execution paths. |
| receipts | Dated evidence of validation, reconciliation, security gates, and execution boundaries. |

Start with:

- [Governance](GOVERNANCE.md)
- [Cognitive invocation contract](contracts/SOA_INTELLIGENCE_COGNITIVE_INVOCATION_v0.1.md)
- [A2 persistence overlay](docs/persistence/SOA_INTELLIGENCE_A2_PERSISTENCE_OVERLAY_v0.1.md)
- [A2 Azure DEV boundary](infra/azure/soa-intelligence-dev/README.md)
- [Production hardening receipt](receipts/ISSUE_19_PROD_HARDENING_2026-09-02.md)

## Security and operational posture

The repository follows several non-negotiable controls:

- PostgreSQL private networking is preferred; public exposure is not a migration shortcut.
- Credentials are not committed to source control and are excluded from traces and receipts where the contract requires it.
- OCI workloads are bound to immutable image digests where the deployment path requires it.
- Provider and tool boundaries fail closed on missing authority, scope drift, identity drift, malformed output, or material effects.
- R2 and R3 actions require explicit human adjudication; the system does not infer authorization from intent alone.
- Receipts preserve what was validated, what was not executed, and which authority was in force.

## What this repository does not claim

This repository does not claim:

- autonomous authority or independent decision rights;
- a general intelligence system;
- production readiness merely because infrastructure or CI exists;
- a completed Google Workspace integration based on documentation alone;
- that a branch, plan, workflow, or receipt substitutes for live operational evidence.

The public standard is simple:

> A claim must not exceed the evidence available to support it.

## Project identity

SOAiaCore is developed by Salvador Osorio under the SOAIACORE-Corporation organization.

- Website: [soaiacore.com](https://soaiacore.com)
- Author and public identity: [Salvador Osorio](https://github.com/Salvador-Osorio)
- Organization: [SOAIACORE-Corporation](https://github.com/SOAIACORE-Corporation)

This README is an orientation surface. The implementation, contracts, workflows, and dated receipts remain the authoritative sources for individual technical claims.
