from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from .candidate_eval import (
    CandidateIdentity,
    CandidateStructuredOutput,
    build_candidate_request,
)
from .cognitive_loop import CognitiveInvocationRequest, ContextBundle, CognitiveOutput, evaluate_cognitive_output
from .golden_eval import GoldenCase
from .hashing import sha256_json


_G3C2B0_ALLOWED_PARTITIONS = frozenset({"development", "validation"})
_ALLOWED_ENDPOINT = ("https", "api.openai.com", 443, "/v1/responses")
_SENSITIVITY_RANK = {
    "PUBLIC": 0,
    "STANDARD": 1,
    "INTERNAL": 1,
    "CONFIDENTIAL": 2,
    "HIGH": 3,
    "RESTRICTED": 4,
    "SECRET": 5,
}
LiveSensitivity = Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL"]
ProviderALiveExecutionMode = Literal["LIVE"]


class ProviderLiveBoundaryError(RuntimeError):
    """Fail-closed error for the G3C2B0 LIVE provider boundary."""


class ProviderLiveTransportError(RuntimeError):
    """Retryable transport error for a later R2-authorized LIVE execution."""


class ProviderALiveConfig(BaseModel):
    """Frozen Provider A deployment profile for the LIVE boundary."""

    model_config = ConfigDict(frozen=True)

    provider: Literal["openai"] = "openai"
    model_id: Literal["gpt-5.6-sol"] = "gpt-5.6-sol"
    profile_version: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    execution_mode: ProviderALiveExecutionMode = "LIVE"
    credential_env: Literal["OPENAI_API_KEY"] = "OPENAI_API_KEY"
    endpoint_url: Literal["https://api.openai.com/v1/responses"] = (
        "https://api.openai.com/v1/responses"
    )
    reasoning_effort: Literal["high"] = "high"
    timeout_seconds: float = Field(default=30.0, gt=0.0, le=120.0)
    max_attempts: int = Field(default=1, ge=1, le=2)
    max_output_tokens: int = Field(default=4096, ge=256, le=32768)

    def identity(self) -> CandidateIdentity:
        return CandidateIdentity(
            provider=self.provider,
            model_id=self.model_id,
            profile_version=self.profile_version,
            adapter_version=self.adapter_version,
            execution_mode=self.execution_mode,
        )


class OutboundDataPolicy(BaseModel):
    """Explicit data-minimization and sensitivity policy applied before any socket call."""

    model_config = ConfigDict(frozen=True)

    max_sensitivity: LiveSensitivity = "INTERNAL"
    memory_field_allowlist: tuple[str, ...] = (
        "memory_id",
        "project_scope",
        "claim",
        "epistemic_class",
        "sensitivity",
    )
    session_payload_allowlist: tuple[str, ...] = ()

    def permits(self, sensitivity: str) -> bool:
        normalized = sensitivity.strip().upper()
        if normalized not in _SENSITIVITY_RANK:
            return False
        return _SENSITIVITY_RANK[normalized] <= _SENSITIVITY_RANK[self.max_sensitivity]


class ProviderAHTTPResponse(BaseModel):
    """Normalized HTTP response metadata; never contains credentials."""

    model_config = ConfigDict(frozen=True)

    status_code: int = Field(ge=100, le=599)
    request_id: str | None = None
    client_request_id: str = Field(min_length=1)
    response_json: dict[str, Any]


class ProviderAHTTPClient(Protocol):
    """Injectable HTTP client so CI can prove zero network use."""

    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> ProviderAHTTPResponse: ...


class UrllibProviderAHTTPClient:
    """Minimal HTTPS client for a later, separately authorized R2 execution."""

    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> ProviderAHTTPResponse:
        _validate_endpoint(url)
        if os.environ.get("SOAIACORE_G3C2B0_NO_OUTBOUND", "").strip() == "1":
            raise ProviderLiveBoundaryError("G3C2B0 CI no-outbound guard is active")
        body = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        request = urllib.request.Request(
            url=url,
            data=body,
            method="POST",
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
                status = int(response.status)
                request_id = response.headers.get("x-request-id")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            raise ProviderLiveTransportError("OpenAI Responses transport failed") from exc

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise ProviderLiveBoundaryError("OpenAI Responses returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise ProviderLiveBoundaryError("OpenAI Responses returned a non-object JSON body")

        return ProviderAHTTPResponse(
            status_code=status,
            request_id=request_id,
            client_request_id=headers["X-Client-Request-Id"],
            response_json=decoded,
        )


def _validate_endpoint(url: str) -> None:
    parsed = urlsplit(url)
    port = parsed.port or 443
    observed = (parsed.scheme, parsed.hostname or "", port, parsed.path)
    if observed != _ALLOWED_ENDPOINT:
        raise ProviderLiveBoundaryError(
            f"outbound endpoint is not allowlisted: {observed!r}"
        )
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ProviderLiveBoundaryError("outbound endpoint contains forbidden URL components")


def _normalize_sensitivity(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderLiveBoundaryError("outbound context item lacks explicit sensitivity")
    normalized = value.strip().upper()
    if normalized not in _SENSITIVITY_RANK:
        raise ProviderLiveBoundaryError(
            f"unknown outbound sensitivity classification: {normalized}"
        )
    return normalized


def _alias_evidence_refs(refs: tuple[str, ...]) -> tuple[tuple[str, ...], dict[str, str]]:
    aliases: list[str] = []
    reverse: dict[str, str] = {}
    for ref in refs:
        alias = f"e{sha256_json({'ref': ref})[:12]}"
        aliases.append(alias)
        reverse[alias] = ref
    return tuple(aliases), reverse


def _minimize_memory(
    context: ContextBundle,
    *,
    policy: OutboundDataPolicy,
) -> tuple[dict[str, Any], ...]:
    minimized: list[dict[str, Any]] = []
    for row in context.memory:
        sensitivity = _normalize_sensitivity(row.get("sensitivity"))
        if not policy.permits(sensitivity):
            raise ProviderLiveBoundaryError(
                f"memory sensitivity {sensitivity} exceeds outbound policy"
            )
        project_scope = row.get("project_scope")
        if project_scope != context.project_scope:
            raise ProviderLiveBoundaryError("cross-project memory blocked before outbound")
        item = {
            key: row[key]
            for key in policy.memory_field_allowlist
            if key in row
        }
        item["sensitivity"] = sensitivity
        minimized.append(item)
    return tuple(minimized)


def _minimize_session(
    context: ContextBundle,
    *,
    policy: OutboundDataPolicy,
) -> tuple[dict[str, Any], ...]:
    minimized: list[dict[str, Any]] = []
    for item in context.session_items:
        sensitivity = _normalize_sensitivity(item.sensitivity)
        if not policy.permits(sensitivity):
            raise ProviderLiveBoundaryError(
                f"session sensitivity {sensitivity} exceeds outbound policy"
            )
        if item.project_scope != context.project_scope:
            raise ProviderLiveBoundaryError("cross-project session item blocked before outbound")
        payload = {
            key: item.payload[key]
            for key in policy.session_payload_allowlist
            if key in item.payload
        }
        minimized.append(
            {
                "item_id": item.item_id,
                "project_scope": item.project_scope,
                "sensitivity": sensitivity,
                "epistemic_class": item.epistemic_class.value,
                "payload": payload,
            }
        )
    return tuple(minimized)


@dataclass(frozen=True)
class PreparedLiveRequest:
    wire_payload: dict[str, Any]
    payload_sha256: str
    evidence_alias_reverse: dict[str, str]
    client_request_id: str


def _candidate_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "content": {"type": "string", "minLength": 1},
            "epistemic_class": {
                "type": "string",
                "enum": [
                    "DOCUMENTED_FACT",
                    "CONFIRMED_CONTEXT",
                    "INFERENCE",
                    "HYPOTHESIS",
                    "WORKING_ASSUMPTION",
                    "STALE_INFORMATION",
                ],
            },
            "disposition": {
                "type": "string",
                "enum": [
                    "EPHEMERAL_INFERENCE",
                    "CLAIM_PROPOSAL",
                    "DECISION_PROPOSAL",
                    "TOOL_REQUEST",
                ],
            },
            "claims": {"type": "array", "items": {"type": "string"}},
            "evidence_refs": {"type": "array", "items": {"type": "string"}},
            "provenance_refs": {"type": "array", "items": {"type": "string"}},
            "contradictions_predicted": {
                "type": "array",
                "items": {"type": "string"},
            },
            "memory_admission_decision": {
                "type": ["string", "null"],
                "enum": ["ADMIT", "REJECT", "DEFER", None],
            },
            "decision_state": {"type": ["string", "null"]},
            "tool_name": {"type": ["string", "null"]},
            "material_effect": {"type": "boolean"},
        },
        "required": [
            "content",
            "epistemic_class",
            "disposition",
            "claims",
            "evidence_refs",
            "provenance_refs",
            "contradictions_predicted",
            "memory_admission_decision",
            "decision_state",
            "tool_name",
            "material_effect",
        ],
        "additionalProperties": False,
    }


def prepare_g3c2b0_live_request(
    *,
    case: GoldenCase,
    context: ContextBundle,
    config: ProviderALiveConfig,
    data_policy: OutboundDataPolicy,
) -> PreparedLiveRequest:
    """Prepare an allowlisted/minimized LIVE request without executing outbound I/O."""

    if case.partition not in _G3C2B0_ALLOWED_PARTITIONS:
        raise ProviderLiveBoundaryError("G3C2B0 Holdout execution is forbidden")
    if case.project_scope != context.project_scope:
        raise ProviderLiveBoundaryError("G3C2B0 case/context project_scope mismatch")
    _validate_endpoint(config.endpoint_url)

    request = build_candidate_request(case=case, context=context)
    evidence_aliases, reverse = _alias_evidence_refs(context.evidence_refs)
    runtime_context = {
        "project_scope": context.project_scope,
        "valid_at": context.valid_at.isoformat(),
        "recorded_at": context.recorded_at.isoformat(),
        "memory": list(_minimize_memory(context, policy=data_policy)),
        "evidence_refs": list(evidence_aliases),
        "session_items": list(_minimize_session(context, policy=data_policy)),
    }
    client_request_id = f"g3c2b0-{sha256_json({'invocation_id': request.invocation_id})[:32]}"
    wire_payload = {
        "model": config.model_id,
        "reasoning": {"effort": config.reasoning_effort},
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": request.messages[0].content}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(
                            {"runtime_context": runtime_context},
                            sort_keys=True,
                            separators=(",", ":"),
                            ensure_ascii=False,
                        ),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "soa_candidate_structured_output",
                "strict": True,
                "schema": _candidate_json_schema(),
            }
        },
        "tools": [],
        "tool_choice": "none",
        "parallel_tool_calls": False,
        "store": False,
        "background": False,
        "max_output_tokens": config.max_output_tokens,
        "truncation": "disabled",
    }
    return PreparedLiveRequest(
        wire_payload=wire_payload,
        payload_sha256=sha256_json(wire_payload),
        evidence_alias_reverse=reverse,
        client_request_id=client_request_id,
    )


def _credential(
    config: ProviderALiveConfig,
    *,
    environment: Mapping[str, str] | None,
) -> str:
    env = environment if environment is not None else os.environ
    value = env.get(config.credential_env, "")
    if not value.strip():
        raise ProviderLiveBoundaryError(
            "Provider A credential missing from runtime OPENAI_API_KEY"
        )
    return value


def _extract_structured_output(response_json: dict[str, Any]) -> dict[str, Any]:
    if response_json.get("status") != "completed":
        raise ProviderLiveBoundaryError("OpenAI Responses result is not completed")
    for item in response_json.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = content.get("text")
                if not isinstance(text, str):
                    continue
                try:
                    decoded = json.loads(text)
                except Exception as exc:
                    raise ProviderLiveBoundaryError(
                        "OpenAI structured output is not valid JSON"
                    ) from exc
                if not isinstance(decoded, dict):
                    raise ProviderLiveBoundaryError(
                        "OpenAI structured output is not a JSON object"
                    )
                return decoded
    raise ProviderLiveBoundaryError("OpenAI response contains no output_text payload")


def _restore_evidence_aliases(
    result: CandidateStructuredOutput,
    reverse: dict[str, str],
) -> CandidateStructuredOutput:
    evidence_refs = tuple(reverse.get(ref, ref) for ref in result.evidence_refs)
    provenance_refs = tuple(
        (
            f"evidence:{reverse.get(ref.removeprefix('evidence:'), ref.removeprefix('evidence:'))}"
            if ref.startswith("evidence:")
            else ref
        )
        for ref in result.provenance_refs
    )
    return result.model_copy(
        update={
            "evidence_refs": evidence_refs,
            "provenance_refs": provenance_refs,
        }
    )


def _to_cognitive_output(
    *,
    request: CognitiveInvocationRequest,
    result: CandidateStructuredOutput,
) -> CognitiveOutput:
    seed = {"invocation_id": request.invocation_id, "result": result.model_dump(mode="json")}
    return CognitiveOutput(
        output_id=f"cout-{sha256_json(seed)[:24]}",
        content=result.content,
        epistemic_class=result.epistemic_class,
        disposition=result.disposition,
        evidence_refs=result.evidence_refs,
        provenance_refs=result.provenance_refs,
        tool_name=result.tool_name,
        material_effect=result.material_effect,
    )


def _critical_provenance_refs(result: CandidateStructuredOutput) -> tuple[str, ...]:
    ordered = list(result.provenance_refs)
    ordered.extend(f"evidence:{ref}" for ref in result.evidence_refs)
    return tuple(dict.fromkeys(ordered))


class ProviderALiveAdapter:
    """LIVE adapter. Outbound execution is impossible unless an R2 permit is supplied."""

    def __init__(
        self,
        *,
        config: ProviderALiveConfig,
        data_policy: OutboundDataPolicy,
        http_client: ProviderAHTTPClient,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.config = config
        self.data_policy = data_policy
        self.http_client = http_client
        self.environment = environment

    @property
    def identity(self) -> CandidateIdentity:
        return self.config.identity()

    def execute(
        self,
        *,
        case: GoldenCase,
        context: ContextBundle,
        r2_authority_ref: str | None = None,
    ) -> dict[str, Any]:
        if not r2_authority_ref or not r2_authority_ref.strip():
            raise ProviderLiveBoundaryError(
                "LIVE outbound execution requires an explicit R2 authority reference"
            )
        prepared = prepare_g3c2b0_live_request(
            case=case,
            context=context,
            config=self.config,
            data_policy=self.data_policy,
        )
        credential = _credential(self.config, environment=self.environment)
        request = build_candidate_request(case=case, context=context)

        response: ProviderAHTTPResponse | None = None
        attempts = 0
        last_error: ProviderLiveTransportError | None = None
        for attempt in range(1, self.config.max_attempts + 1):
            attempts = attempt
            try:
                response = self.http_client.post_json(
                    url=self.config.endpoint_url,
                    headers={
                        "Authorization": f"Bearer {credential}",
                        "Content-Type": "application/json",
                        "X-Client-Request-Id": prepared.client_request_id,
                    },
                    payload=prepared.wire_payload,
                    timeout_seconds=self.config.timeout_seconds,
                )
                break
            except ProviderLiveTransportError as exc:
                last_error = exc
        if response is None:
            raise ProviderLiveBoundaryError(
                f"Provider A LIVE transport exhausted {attempts} attempt(s)"
            ) from last_error
        if response.status_code < 200 or response.status_code >= 300:
            raise ProviderLiveBoundaryError(
                f"Provider A LIVE transport returned HTTP {response.status_code}"
            )
        if not response.request_id:
            raise ProviderLiveBoundaryError("Provider A LIVE response is missing x-request-id")
        if response.client_request_id != prepared.client_request_id:
            raise ProviderLiveBoundaryError("Provider A LIVE client request ID drift")
        if response.response_json.get("model") != self.config.model_id:
            raise ProviderLiveBoundaryError("Provider A LIVE model identity drift")
        raw_output = _extract_structured_output(response.response_json)
        try:
            result = CandidateStructuredOutput.model_validate(raw_output)
        except Exception as exc:
            raise ProviderLiveBoundaryError(
                "Provider A LIVE structured output validation failed"
            ) from exc
        result = _restore_evidence_aliases(result, prepared.evidence_alias_reverse)
        if result.tool_name is not None or result.material_effect:
            raise ProviderLiveBoundaryError(
                "Provider A LIVE candidate attempted a forbidden tool/material effect"
            )

        output = _to_cognitive_output(request=request, result=result)
        policy = evaluate_cognitive_output(output)
        output_body = output.model_dump(mode="json")
        output_body["claims"] = list(result.claims)
        body = {
            "golden_case_id": case.golden_case_id,
            "partition": case.partition,
            "candidate": self.identity.model_dump(mode="json"),
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
            "transport_attempt_count": attempts,
            "external_provider_calls": 1,
            "oracle_fields_exposed": False,
            "holdout_executed": False,
            "tools_enabled": False,
            "provider_boundary_version": "g3c-provider-a-live/0.1",
            "provider_response_id": str(response.response_json.get("id", "")),
            "provider_request_id": response.request_id,
            "client_request_id": response.client_request_id,
            "provider_reported_model": str(response.response_json.get("model", "")),
            "payload_sha256": prepared.payload_sha256,
            "r2_authority_ref": r2_authority_ref.strip(),
        }
        return {**body, "trace_sha256": sha256_json(body)}


def validate_live_trace(
    *,
    trace: dict[str, Any],
    expected_identity: CandidateIdentity,
) -> dict[str, str]:
    trace_sha = trace.get("trace_sha256")
    if not isinstance(trace_sha, str) or len(trace_sha) != 64:
        raise ProviderLiveBoundaryError("LIVE trace digest is missing or malformed")
    body = {key: value for key, value in trace.items() if key != "trace_sha256"}
    if sha256_json(body) != trace_sha:
        raise ProviderLiveBoundaryError("LIVE trace digest mismatch")
    if trace.get("candidate") != expected_identity.model_dump(mode="json"):
        raise ProviderLiveBoundaryError("LIVE provider identity drift")
    if trace.get("external_provider_calls") != 1:
        raise ProviderLiveBoundaryError("LIVE trace must represent exactly one provider call")
    if trace.get("holdout_executed") is not False:
        raise ProviderLiveBoundaryError("LIVE trace indicates Holdout execution")
    if trace.get("oracle_fields_exposed") is not False:
        raise ProviderLiveBoundaryError("candidate/oracle separation not proven")
    payload_sha = trace.get("payload_sha256")
    if not isinstance(payload_sha, str) or len(payload_sha) != 64:
        raise ProviderLiveBoundaryError("LIVE payload digest is missing or malformed")
    client_request_id = trace.get("client_request_id")
    if not isinstance(client_request_id, str) or not client_request_id:
        raise ProviderLiveBoundaryError("LIVE client request ID missing")
    return {
        "golden_case_id": str(trace.get("golden_case_id", "")),
        "trace_sha256": trace_sha,
        "payload_sha256": payload_sha,
        "client_request_id": client_request_id,
        "provider_request_id": str(trace.get("provider_request_id") or ""),
    }


def live_provider_trace_receipt(
    *,
    traces: tuple[dict[str, Any], ...],
    expected_identity: CandidateIdentity,
    expected_r2_authority_ref: str,
) -> dict[str, Any]:
    """Deterministic receipt for a future R2 LIVE dev/validation run; never claims G3 PASS."""

    if not traces:
        raise ProviderLiveBoundaryError("LIVE receipt requires at least one trace")
    if any(trace.get("partition") not in _G3C2B0_ALLOWED_PARTITIONS for trace in traces):
        raise ProviderLiveBoundaryError("LIVE receipt contains Holdout execution")
    if any(trace.get("r2_authority_ref") != expected_r2_authority_ref for trace in traces):
        raise ProviderLiveBoundaryError("LIVE receipt authority mismatch")

    refs = tuple(
        sorted(
            (
                validate_live_trace(trace=trace, expected_identity=expected_identity)
                for trace in traces
            ),
            key=lambda item: item["golden_case_id"],
        )
    )
    ids = [ref["golden_case_id"] for ref in refs]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ProviderLiveBoundaryError("LIVE trace IDs must be unique and non-empty")
    counts = Counter(str(trace["partition"]) for trace in traces)
    body = {
        "candidate": expected_identity.model_dump(mode="json"),
        "r2_authority_ref": expected_r2_authority_ref,
        "case_count": len(traces),
        "partition_counts": {
            "development": counts["development"],
            "validation": counts["validation"],
            "holdout": 0,
        },
        "candidate_call_count": len(traces),
        "transport_attempt_count": sum(int(trace["transport_attempt_count"]) for trace in traces),
        "external_provider_calls": len(traces),
        "oracle_fields_exposed": False,
        "holdout_executed": False,
        "tools_enabled": False,
        "g3_quality_pass_claimed": False,
        "trace_refs": refs,
    }
    return {**body, "receipt_sha256": sha256_json(body)}
