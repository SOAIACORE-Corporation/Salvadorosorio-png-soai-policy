from __future__ import annotations

import os
from collections import Counter
from collections.abc import Mapping
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .candidate_eval import (
    CandidateIdentity,
    CandidateStructuredOutput,
    MemoryAdmissionDecision,
    build_candidate_request,
)
from .cognitive_loop import (
    CognitiveInvocationRequest,
    CognitiveOutput,
    ContextBundle,
    evaluate_cognitive_output,
)
from .golden_eval import GoldenCase
from .hashing import sha256_json


_G3C2A_ALLOWED_PARTITIONS = frozenset({"development", "validation"})
ProviderAExecutionMode = Literal["REPLAY"]


class ProviderTransportError(RuntimeError):
    """Retryable failure raised by a provider transport implementation."""


class ProviderExecutionError(RuntimeError):
    """Fail-closed provider boundary error."""


class ProviderATransport(Protocol):
    """Injectable Provider A transport.

    G3C2A accepts only transports that explicitly report external=False. A later,
    separately authorized increment may add a real outbound transport.
    """

    @property
    def external(self) -> bool: ...

    def send(
        self,
        *,
        payload: dict[str, Any],
        credential: str,
    ) -> dict[str, Any]: ...


class ProviderAConfig(BaseModel):
    """Versioned deployment profile for the first concrete provider boundary."""

    model_config = ConfigDict(frozen=True)

    provider: Literal["openai"] = "openai"
    model_id: str = Field(min_length=1)
    profile_version: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    execution_mode: ProviderAExecutionMode = "REPLAY"
    credential_env: str = Field(default="OPENAI_API_KEY", min_length=1)
    max_attempts: int = Field(default=2, ge=1, le=3)

    def identity(self) -> CandidateIdentity:
        return CandidateIdentity(
            provider=self.provider,
            model_id=self.model_id,
            profile_version=self.profile_version,
            adapter_version=self.adapter_version,
            execution_mode=self.execution_mode,
        )


class ProviderAAdapter:
    """Provider A candidate adapter with an injectable, non-external G3C2A transport."""

    def __init__(
        self,
        *,
        config: ProviderAConfig,
        transport: ProviderATransport,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self._config = config
        self._transport = transport
        self._environment = environment
        self._last_attempt_count = 0

    @property
    def identity(self) -> CandidateIdentity:
        return self._config.identity()

    @property
    def last_attempt_count(self) -> int:
        return self._last_attempt_count

    def _credential(self) -> str:
        environment = self._environment if self._environment is not None else os.environ
        value = environment.get(self._config.credential_env, "")
        if not value.strip():
            raise ProviderExecutionError(
                f"provider credential missing from runtime env {self._config.credential_env}"
            )
        return value

    @staticmethod
    def _context_payload(context: ContextBundle) -> dict[str, Any]:
        return {
            "project_scope": context.project_scope,
            "valid_at": context.valid_at.isoformat(),
            "recorded_at": context.recorded_at.isoformat(),
            "memory": [dict(item) for item in context.memory],
            "evidence_refs": list(context.evidence_refs),
            "session_items": [
                {
                    "item_id": item.item_id,
                    "project_scope": item.project_scope,
                    "payload": dict(item.payload),
                    "sensitivity": item.sensitivity,
                    "epistemic_class": item.epistemic_class.value,
                    "created_at": item.created_at.isoformat(),
                    "expires_at": item.expires_at.isoformat(),
                }
                for item in context.session_items
            ],
        }

    def _wire_payload(
        self,
        *,
        request: CognitiveInvocationRequest,
        context: ContextBundle,
    ) -> dict[str, Any]:
        return {
            "provider": self._config.provider,
            "model": self._config.model_id,
            "profile_version": self._config.profile_version,
            "messages": [message.model_dump(mode="json") for message in request.messages],
            "context": self._context_payload(context),
            "response_contract": {
                "schema": request.output_schema,
                "required": ["content", "epistemic_class", "disposition"],
                "optional": [
                    "claims",
                    "evidence_refs",
                    "provenance_refs",
                    "contradictions_predicted",
                    "memory_admission_decision",
                    "decision_state",
                    "tool_name",
                    "material_effect",
                ],
            },
            "tools": [],
            "tool_choice": "none",
            "trace": {
                "invocation_id": request.invocation_id,
                "evaluation_contract": "g3c-provider-a/0.1",
            },
        }

    def invoke(
        self,
        request: CognitiveInvocationRequest,
        context: ContextBundle,
    ) -> CandidateStructuredOutput:
        if self._transport.external:
            raise ProviderExecutionError(
                "G3C2A forbids external provider transport; R2 provider execution is required"
            )
        if request.tool_contracts:
            raise ProviderExecutionError("G3C2A provider benchmark forbids tool contracts")

        credential = self._credential()
        payload = self._wire_payload(request=request, context=context)
        self._last_attempt_count = 0
        response: dict[str, Any] | None = None
        last_error: ProviderTransportError | None = None

        for attempt in range(1, self._config.max_attempts + 1):
            self._last_attempt_count = attempt
            try:
                response = self._transport.send(payload=payload, credential=credential)
                break
            except ProviderTransportError as exc:
                last_error = exc

        if response is None:
            raise ProviderExecutionError(
                f"provider transport exhausted {self._last_attempt_count} attempt(s)"
            ) from last_error
        if not isinstance(response, dict):
            raise ProviderExecutionError("provider transport returned a non-object payload")

        try:
            result = CandidateStructuredOutput.model_validate(response)
        except Exception as exc:
            raise ProviderExecutionError("provider structured output validation failed") from exc

        if result.tool_name is not None or result.material_effect:
            raise ProviderExecutionError("provider candidate attempted a forbidden tool/material effect")
        return result


def _to_cognitive_output(
    *,
    request: CognitiveInvocationRequest,
    result: CandidateStructuredOutput,
) -> CognitiveOutput:
    seed = {
        "invocation_id": request.invocation_id,
        "result": result.model_dump(mode="json"),
    }
    return CognitiveOutput(
        output_id=f"cout-{sha256_json(seed)[:24]}",
        content=result.content,
        epistemic_class=result.epistemic_class,
        disposition=result.disposition,
        evidence_refs=result.evidence_refs,
        provenance_refs=result.provenance_refs,
        tool_name=None,
        material_effect=False,
    )


def _critical_provenance_refs(result: CandidateStructuredOutput) -> tuple[str, ...]:
    ordered = list(result.provenance_refs)
    ordered.extend(f"evidence:{ref}" for ref in result.evidence_refs)
    return tuple(dict.fromkeys(ordered))


def execute_g3c2a_provider_case(
    *,
    case: GoldenCase,
    context: ContextBundle,
    adapter: ProviderAAdapter,
) -> dict[str, Any]:
    """Capture one Provider A replay trace without external calls or Holdout access."""

    if case.partition not in _G3C2A_ALLOWED_PARTITIONS:
        raise ProviderExecutionError("G3C2A Holdout execution is forbidden")
    if adapter.identity.execution_mode != "REPLAY":
        raise ProviderExecutionError("G3C2A permits REPLAY execution only")
    if case.project_scope != context.project_scope:
        raise ProviderExecutionError("G3C2A case/context project_scope mismatch")

    request = build_candidate_request(case=case, context=context)
    result = adapter.invoke(request, context)
    output = _to_cognitive_output(request=request, result=result)
    policy = evaluate_cognitive_output(output)

    output_body = output.model_dump(mode="json")
    output_body["claims"] = list(result.claims)
    body: dict[str, Any] = {
        "golden_case_id": case.golden_case_id,
        "partition": case.partition,
        "candidate": adapter.identity.model_dump(mode="json"),
        "invocation_id": request.invocation_id,
        "project_scope": context.project_scope,
        "valid_at": context.valid_at.isoformat(),
        "recorded_at": context.recorded_at.isoformat(),
        "context_refs": list(context.context_refs),
        "output": output_body,
        "policy": {
            "action": policy.action.value,
            "canonical_write_allowed": policy.canonical_write_allowed,
            "material_action_executed": policy.material_action_executed,
            "reason_codes": list(policy.reason_codes),
        },
        "quality_signals": {
            "critical_provenance_refs": list(_critical_provenance_refs(result)),
            "contradictions_predicted": list(result.contradictions_predicted),
            "memory_admission_decision": result.memory_admission_decision,
            "decision_state": result.decision_state,
            "schema_valid": True,
        },
        "candidate_call_count": 1,
        "transport_attempt_count": adapter.last_attempt_count,
        "external_provider_calls": 0,
        "oracle_fields_exposed": False,
        "holdout_executed": False,
        "tools_enabled": False,
        "provider_boundary_version": "g3c-provider-a/0.1",
    }
    return {**body, "trace_sha256": sha256_json(body)}


def execute_g3c2a_provider_dataset(
    *,
    cases: tuple[GoldenCase, ...],
    contexts_by_case_id: dict[str, ContextBundle],
    adapter: ProviderAAdapter,
) -> tuple[dict[str, Any], ...]:
    """Execute exact development/validation coverage through the mock Provider A boundary."""

    if not cases:
        raise ProviderExecutionError("G3C2A provider dataset cannot be empty")
    case_ids = [case.golden_case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ProviderExecutionError("duplicate golden_case_id in G3C2A input")
    if any(case.partition not in _G3C2A_ALLOWED_PARTITIONS for case in cases):
        raise ProviderExecutionError("G3C2A dataset contains a forbidden Holdout case")

    expected = set(case_ids)
    observed = set(contexts_by_case_id)
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    if missing or extra:
        raise ProviderExecutionError(
            f"G3C2A context coverage mismatch; missing={missing}, extra={extra}"
        )

    return tuple(
        execute_g3c2a_provider_case(
            case=case,
            context=contexts_by_case_id[case.golden_case_id],
            adapter=adapter,
        )
        for case in cases
    )


def _validated_trace_ref(trace: dict[str, Any]) -> dict[str, str]:
    trace_sha = trace.get("trace_sha256")
    if not isinstance(trace_sha, str) or len(trace_sha) != 64:
        raise ProviderExecutionError("provider trace digest is missing or malformed")
    body = {key: value for key, value in trace.items() if key != "trace_sha256"}
    if sha256_json(body) != trace_sha:
        raise ProviderExecutionError("provider trace digest mismatch")
    if trace.get("external_provider_calls") != 0:
        raise ProviderExecutionError("G3C2A trace indicates an external provider call")
    if trace.get("holdout_executed") is not False:
        raise ProviderExecutionError("G3C2A trace indicates Holdout execution")
    if trace.get("oracle_fields_exposed") is not False:
        raise ProviderExecutionError("candidate/oracle separation not proven")
    return {
        "golden_case_id": str(trace.get("golden_case_id", "")),
        "trace_sha256": trace_sha,
    }


def provider_trace_receipt(
    *,
    traces: tuple[dict[str, Any], ...],
    expected_identity: CandidateIdentity,
) -> dict[str, Any]:
    """Deterministic G3C2A receipt bound to candidate identity and trace digests."""

    if not traces:
        raise ProviderExecutionError("provider trace receipt requires at least one trace")
    expected_identity_sha = sha256_json(expected_identity.model_dump(mode="json"))
    identities = {sha256_json(trace.get("candidate", {})) for trace in traces}
    if identities != {expected_identity_sha}:
        raise ProviderExecutionError("provider identity drift across traces")
    if any(trace.get("partition") not in _G3C2A_ALLOWED_PARTITIONS for trace in traces):
        raise ProviderExecutionError("provider receipt contains Holdout execution")

    trace_refs = tuple(
        sorted(
            (_validated_trace_ref(trace) for trace in traces),
            key=lambda item: item["golden_case_id"],
        )
    )
    case_ids = [item["golden_case_id"] for item in trace_refs]
    if not all(case_ids) or len(case_ids) != len(set(case_ids)):
        raise ProviderExecutionError("provider trace IDs must be unique and non-empty")

    counts = Counter(str(trace["partition"]) for trace in traces)
    body = {
        "candidate": expected_identity.model_dump(mode="json"),
        "case_count": len(traces),
        "partition_counts": {
            "development": counts["development"],
            "validation": counts["validation"],
            "holdout": 0,
        },
        "candidate_call_count": len(traces),
        "transport_attempt_count": sum(int(trace["transport_attempt_count"]) for trace in traces),
        "external_provider_calls": 0,
        "oracle_fields_exposed": False,
        "holdout_executed": False,
        "tools_enabled": False,
        "g3_quality_pass_claimed": False,
        "trace_refs": trace_refs,
    }
    return {**body, "receipt_sha256": sha256_json(body)}
