from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .hashing import sha256_json


class AdmissionDecision(StrEnum):
    ADMIT = "ADMIT"
    REJECT = "REJECT"
    DEFER = "DEFER"


class MemoryCandidateKind(StrEnum):
    DIRECT_DURABLE_PREFERENCE = "DIRECT_DURABLE_PREFERENCE"
    ONE_OFF_DETAIL = "ONE_OFF_DETAIL"
    SECRET = "SECRET"
    HUMAN_INFERENCE = "HUMAN_INFERENCE"
    HUMAN_CONSTRAINT = "HUMAN_CONSTRAINT"
    CANONICAL_POLICY = "CANONICAL_POLICY"
    DUPLICATE_FACT = "DUPLICATE_FACT"
    TOOL_OUTPUT = "TOOL_OUTPUT"


class MemoryAdmissionCandidate(BaseModel):
    """C-09 candidate presented to the Alpha memory admission boundary."""

    model_config = ConfigDict(frozen=True)
    candidate_ref: str = Field(min_length=1)
    project_scope: str = Field(min_length=1)
    kind: MemoryCandidateKind
    sensitivity: str = Field(min_length=1)
    durable: bool = False
    decision_relevant: bool = False
    canonical_authority: bool = False
    explicit_first_person: bool = False
    human_confirmed: bool = False
    provenance_refs: tuple[str, ...] = ()


class MemoryAdmissionDecision(BaseModel):
    """Versioned deterministic C-09 decision; it never performs persistence."""

    model_config = ConfigDict(frozen=True)
    contract_version: str = "memory-admission/0.1"
    candidate_ref: str
    decision: AdmissionDecision
    target_core: str | None = None
    reason_codes: tuple[str, ...]
    receipt_required_before_persist: bool
    persistence_executed: bool = False


def evaluate_memory_admission(candidate: MemoryAdmissionCandidate) -> MemoryAdmissionDecision:
    sensitivity = candidate.sensitivity.strip().upper()

    if sensitivity == "SECRET" or candidate.kind is MemoryCandidateKind.SECRET:
        return MemoryAdmissionDecision(
            candidate_ref=candidate.candidate_ref,
            decision=AdmissionDecision.REJECT,
            reason_codes=("SECRET_MEMORY_ADMISSION_FORBIDDEN",),
            receipt_required_before_persist=False,
        )

    if candidate.kind is MemoryCandidateKind.HUMAN_INFERENCE:
        if not candidate.human_confirmed:
            return MemoryAdmissionDecision(
                candidate_ref=candidate.candidate_ref,
                decision=AdmissionDecision.REJECT,
                reason_codes=("UNCONFIRMED_HUMAN_INFERENCE_NOT_ADMISSIBLE",),
                receipt_required_before_persist=False,
            )
        return MemoryAdmissionDecision(
            candidate_ref=candidate.candidate_ref,
            decision=AdmissionDecision.DEFER,
            reason_codes=("CONFIRMED_HUMAN_INFERENCE_REQUIRES_DOMAIN_REVIEW",),
            receipt_required_before_persist=False,
        )

    if candidate.kind is MemoryCandidateKind.HUMAN_CONSTRAINT:
        if not candidate.explicit_first_person:
            return MemoryAdmissionDecision(
                candidate_ref=candidate.candidate_ref,
                decision=AdmissionDecision.REJECT,
                reason_codes=("HUMAN_CONSTRAINT_REQUIRES_EXPLICIT_FIRST_PERSON_SOURCE",),
                receipt_required_before_persist=False,
            )
        return MemoryAdmissionDecision(
            candidate_ref=candidate.candidate_ref,
            decision=AdmissionDecision.ADMIT,
            target_core="canonical",
            reason_codes=("EXPLICIT_HUMAN_CONSTRAINT", "RESTRICTED_RETRIEVAL_REQUIRED"),
            receipt_required_before_persist=True,
        )

    if candidate.kind is MemoryCandidateKind.DIRECT_DURABLE_PREFERENCE:
        if candidate.durable and candidate.decision_relevant and candidate.provenance_refs:
            return MemoryAdmissionDecision(
                candidate_ref=candidate.candidate_ref,
                decision=AdmissionDecision.ADMIT,
                target_core="canonical",
                reason_codes=("DURABLE_DECISION_RELEVANT_PREFERENCE",),
                receipt_required_before_persist=True,
            )
        return MemoryAdmissionDecision(
            candidate_ref=candidate.candidate_ref,
            decision=AdmissionDecision.DEFER,
            reason_codes=("DURABILITY_OR_PROVENANCE_INSUFFICIENT",),
            receipt_required_before_persist=False,
        )

    if candidate.kind is MemoryCandidateKind.CANONICAL_POLICY:
        if candidate.canonical_authority and candidate.provenance_refs:
            return MemoryAdmissionDecision(
                candidate_ref=candidate.candidate_ref,
                decision=AdmissionDecision.DEFER,
                reason_codes=("R2_CANONICAL_POLICY_GATE_REQUIRED",),
                receipt_required_before_persist=False,
            )
        return MemoryAdmissionDecision(
            candidate_ref=candidate.candidate_ref,
            decision=AdmissionDecision.REJECT,
            reason_codes=("CANONICAL_AUTHORITY_OR_PROVENANCE_MISSING",),
            receipt_required_before_persist=False,
        )

    if candidate.kind is MemoryCandidateKind.DUPLICATE_FACT:
        return MemoryAdmissionDecision(
            candidate_ref=candidate.candidate_ref,
            decision=AdmissionDecision.DEFER,
            reason_codes=("RELATE_OR_MERGE_EXISTING_RECORD",),
            receipt_required_before_persist=False,
        )

    if candidate.kind is MemoryCandidateKind.TOOL_OUTPUT:
        return MemoryAdmissionDecision(
            candidate_ref=candidate.candidate_ref,
            decision=AdmissionDecision.DEFER,
            reason_codes=("TEMPORARY_TOOL_OUTPUT_BUFFER_ONLY",),
            receipt_required_before_persist=False,
        )

    return MemoryAdmissionDecision(
        candidate_ref=candidate.candidate_ref,
        decision=AdmissionDecision.REJECT,
        reason_codes=("ONE_OFF_DETAIL_NOT_DURABLE",),
        receipt_required_before_persist=False,
    )


class EffectClass(StrEnum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"


class GatewayAction(StrEnum):
    ALLOW_R0 = "ALLOW_R0"
    ALLOW_R1 = "ALLOW_R1"
    HOLD_R2 = "HOLD_R2"
    HOLD_R2_READY = "HOLD_R2_READY"
    DENY_R3 = "DENY_R3"
    DENY_SCOPE = "DENY_SCOPE"
    DENY_INVALID = "DENY_INVALID"
    BLOCK_RETRY = "BLOCK_RETRY"


class ToolInvocation(BaseModel):
    """C-12 provider-neutral tool request. Evaluation never executes the tool."""

    model_config = ConfigDict(frozen=True)
    contract_version: str = "tool-invocation/0.1"
    tool_call_id: str = Field(min_length=1)
    tool_id: str = Field(min_length=1)
    effect_class: EffectClass
    scope: tuple[str, ...]
    arguments: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    approval_ref: str | None = None
    approval_issued_at: datetime | None = None
    requested_by: str = Field(min_length=1)
    untrusted_tool_description: str = ""

    @field_validator("approval_issued_at")
    @classmethod
    def approval_time_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("approval_issued_at must be timezone-aware")
        return value


class ToolGatewayDecision(BaseModel):
    model_config = ConfigDict(frozen=True)
    contract_version: str = "action-gateway/0.1"
    tool_call_id: str
    action: GatewayAction
    reason_codes: tuple[str, ...]
    material_action_executed: bool = False
    receipt_sha256: str


def evaluate_tool_invocation(
    invocation: ToolInvocation,
    *,
    allowed_tools: tuple[str, ...],
    allowed_scope: tuple[str, ...],
    now: datetime,
    approval_freshness_seconds: int = 900,
    seen_idempotency_keys: tuple[str, ...] = (),
) -> ToolGatewayDecision:
    """Evaluate C-12 fail-closed without producing external effects."""

    current = _as_utc(now)
    reasons: list[str] = []
    if invocation.untrusted_tool_description:
        reasons.append("UNTRUSTED_TOOL_DESCRIPTION_IGNORED")

    if invocation.tool_id not in set(allowed_tools):
        return _gateway_decision(invocation, GatewayAction.DENY_INVALID, reasons + ["TOOL_NOT_ALLOWLISTED"])

    if not set(invocation.scope).issubset(set(allowed_scope)):
        return _gateway_decision(invocation, GatewayAction.DENY_SCOPE, reasons + ["REQUESTED_SCOPE_OUTSIDE_ALLOWLIST"])

    if invocation.effect_class is EffectClass.R3:
        return _gateway_decision(invocation, GatewayAction.DENY_R3, reasons + ["R3_UNAVAILABLE_IN_ALPHA"])

    if invocation.effect_class is EffectClass.R0:
        return _gateway_decision(invocation, GatewayAction.ALLOW_R0, reasons + ["R0_READ_ONLY_IN_SCOPE"])

    if invocation.effect_class is EffectClass.R1:
        if not invocation.idempotency_key:
            return _gateway_decision(invocation, GatewayAction.DENY_INVALID, reasons + ["R1_IDEMPOTENCY_KEY_REQUIRED"])
        if invocation.idempotency_key in set(seen_idempotency_keys):
            return _gateway_decision(invocation, GatewayAction.BLOCK_RETRY, reasons + ["IDEMPOTENT_RETRY_BLOCKED"])
        return _gateway_decision(invocation, GatewayAction.ALLOW_R1, reasons + ["R1_REVERSIBLE_INTERNAL_ONLY"])

    if not invocation.approval_ref or invocation.approval_issued_at is None:
        return _gateway_decision(invocation, GatewayAction.HOLD_R2, reasons + ["R2_APPROVAL_REQUIRED"])

    approved_at = _as_utc(invocation.approval_issued_at)
    age_seconds = (current - approved_at).total_seconds()
    if age_seconds < 0 or age_seconds > approval_freshness_seconds:
        return _gateway_decision(invocation, GatewayAction.HOLD_R2, reasons + ["R2_APPROVAL_STALE"])

    return _gateway_decision(
        invocation,
        GatewayAction.HOLD_R2_READY,
        reasons + ["R2_APPROVAL_FRESH_BUT_EXECUTION_OUTSIDE_ALPHA_REFERENCE_GATEWAY"],
    )


def g2_safety_receipt(*, dataset_id: str, case_results: dict[str, bool]) -> dict[str, Any]:
    ordered = {key: bool(case_results[key]) for key in sorted(case_results)}
    body = {
        "dataset_id": dataset_id,
        "case_count": len(ordered),
        "passed_cases": sum(1 for passed in ordered.values() if passed),
        "failed_cases": [key for key, passed in ordered.items() if not passed],
        "g2_safety_pass": all(ordered.values()) and bool(ordered),
        "external_provider_calls": 0,
        "material_actions_executed": 0,
        "case_results": ordered,
    }
    return {**body, "receipt_sha256": sha256_json(body)}


def _gateway_decision(
    invocation: ToolInvocation,
    action: GatewayAction,
    reasons: list[str],
) -> ToolGatewayDecision:
    body = {
        "contract_version": "action-gateway/0.1",
        "tool_call_id": invocation.tool_call_id,
        "action": action.value,
        "reason_codes": reasons,
        "material_action_executed": False,
    }
    return ToolGatewayDecision(
        **body,
        receipt_sha256=sha256_json(body),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime values must be timezone-aware")
    return value.astimezone(timezone.utc)
