from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

from soaiacore_runtime.cognitive_loop import (
    ContextBundle,
    EpistemicClass,
    OutputDisposition,
    SessionBufferItem,
)
from soaiacore_runtime.golden_eval import GoldenCase
from soaiacore_runtime.provider_live import (
    OutboundDataPolicy,
    ProviderAHTTPResponse,
    ProviderALiveAdapter,
    ProviderALiveConfig,
    ProviderLiveBoundaryError,
    ProviderLiveTransportError,
    UrllibProviderAHTTPClient,
    _validate_endpoint,
    live_provider_trace_receipt,
    prepare_g3c2b0_live_request,
)


NOW = datetime(2026, 9, 8, 21, 0, tzinfo=timezone.utc)
API_KEY = "runtime-live-placeholder-not-a-real-key"


def _config(*, max_attempts: int = 1) -> ProviderALiveConfig:
    return ProviderALiveConfig(
        profile_version="g3c2b0-live-profile/0.1",
        adapter_version="provider-a-live-boundary/0.1",
        max_attempts=max_attempts,
    )


def _case(case_id: str, partition: str = "development") -> GoldenCase:
    return GoldenCase(
        golden_case_id=case_id,
        project_scope="SOAiaCore",
        question="What is the governed state from this context?",
        cutoff_time=NOW,
        allowed_evidence_refs=("private-source-ref",),
        forbidden_future_refs=("ORACLE_FUTURE",),
        expected_epistemic_class=EpistemicClass.CONFIRMED_CONTEXT,
        expected_claims=("ORACLE_EXPECTED_CLAIM",),
        expected_decision_state="ADMIT",
        contradictions_expected=("ORACLE_CONTRADICTION",),
        required_provenance=("private-source-ref",),
        forbidden_tool_classes=("ORACLE_TOOL",),
        notes="ORACLE_NOTES",
        partition=partition,
    )


def _context(
    *,
    memory_sensitivity: str = "INTERNAL",
    session_sensitivity: str = "INTERNAL",
) -> ContextBundle:
    session = SessionBufferItem(
        item_id="S-1",
        session_id="session-1",
        project_scope="SOAiaCore",
        payload={
            "approved_text": "synthetic session context",
            "extra_private_field": "MUST_NOT_CROSS_BOUNDARY",
        },
        sensitivity=session_sensitivity,
        epistemic_class=EpistemicClass.CONFIRMED_CONTEXT,
        created_at=NOW,
        expires_at=NOW.replace(day=9),
    )
    return ContextBundle(
        project_scope="SOAiaCore",
        valid_at=NOW,
        recorded_at=NOW,
        memory=(
            {
                "memory_id": "M-1",
                "project_scope": "SOAiaCore",
                "claim": "synthetic governed memory",
                "epistemic_class": "CONFIRMED_CONTEXT",
                "sensitivity": memory_sensitivity,
                "raw_payload": "MUST_NOT_CROSS_BOUNDARY",
            },
        ),
        evidence_refs=("private-source-ref",),
        session_items=(session,),
    )


def _candidate_body() -> dict[str, Any]:
    return {
        "content": "The governed state is confirmed by the supplied context.",
        "epistemic_class": EpistemicClass.CONFIRMED_CONTEXT.value,
        "disposition": OutputDisposition.CLAIM_PROPOSAL.value,
        "claims": ["governed state confirmed"],
        "evidence_refs": [],
        "provenance_refs": [],
        "contradictions_predicted": [],
        "memory_admission_decision": "ADMIT",
        "decision_state": "ADMIT",
        "tool_name": None,
        "material_effect": False,
    }


def _responses_envelope(
    *,
    model: str = "gpt-5.6-sol",
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": "resp_fixture_001",
        "object": "response",
        "status": "completed",
        "model": model,
        "output": [
            {
                "type": "message",
                "id": "msg_fixture_001",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(body or _candidate_body(), sort_keys=True),
                    }
                ],
            }
        ],
    }


class RecordingHTTPClient:
    def __init__(
        self,
        *,
        responses: list[ProviderAHTTPResponse | Exception] | None = None,
    ) -> None:
        self.responses = list(responses or [])
        self.calls: list[dict[str, Any]] = []

    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> ProviderAHTTPResponse:
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        if not self.responses:
            raise AssertionError("fake HTTP client exhausted")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _success_response(client_request_id: str) -> ProviderAHTTPResponse:
    return ProviderAHTTPResponse(
        status_code=200,
        request_id="req_fixture_001",
        client_request_id=client_request_id,
        response_json=_responses_envelope(),
    )


def test_live_profile_is_frozen_to_authorized_openai_contract():
    config = _config()
    assert config.provider == "openai"
    assert config.model_id == "gpt-5.6-sol"
    assert config.execution_mode == "LIVE"
    assert config.credential_env == "OPENAI_API_KEY"
    assert config.endpoint_url == "https://api.openai.com/v1/responses"
    assert config.reasoning_effort == "high"
    assert config.max_attempts == 1


def test_prepare_live_request_is_no_outbound_minimized_and_strict():
    policy = OutboundDataPolicy(session_payload_allowlist=("approved_text",))
    prepared = prepare_g3c2b0_live_request(
        case=_case("DEV-PREPARE"),
        context=_context(),
        config=_config(),
        data_policy=policy,
    )

    wire = prepared.wire_payload
    serialized = json.dumps(wire, sort_keys=True)
    assert wire["model"] == "gpt-5.6-sol"
    assert wire["reasoning"] == {"effort": "high"}
    assert wire["store"] is False
    assert wire["background"] is False
    assert wire["tools"] == []
    assert wire["tool_choice"] == "none"
    assert wire["parallel_tool_calls"] is False
    assert wire["truncation"] == "disabled"
    assert wire["text"]["format"]["type"] == "json_schema"
    assert wire["text"]["format"]["strict"] is True
    assert wire["text"]["format"]["schema"]["additionalProperties"] is False
    assert "ORACLE_EXPECTED_CLAIM" not in serialized
    assert "ORACLE_CONTRADICTION" not in serialized
    assert "ORACLE_FUTURE" not in serialized
    assert "ORACLE_NOTES" not in serialized
    assert "MUST_NOT_CROSS_BOUNDARY" not in serialized
    assert "private-source-ref" not in serialized
    assert "approved_text" in serialized
    assert API_KEY not in serialized
    assert len(prepared.payload_sha256) == 64
    assert prepared.client_request_id.startswith("g3c2b0-")


def test_prepare_live_request_rejects_confidential_by_default():
    with pytest.raises(ProviderLiveBoundaryError, match="CONFIDENTIAL exceeds outbound policy"):
        prepare_g3c2b0_live_request(
            case=_case("DEV-CONFIDENTIAL-BLOCK"),
            context=_context(memory_sensitivity="CONFIDENTIAL"),
            config=_config(),
            data_policy=OutboundDataPolicy(),
        )


def test_prepare_live_request_rejects_restricted_even_when_confidential_is_allowed():
    with pytest.raises(ProviderLiveBoundaryError, match="RESTRICTED exceeds outbound policy"):
        prepare_g3c2b0_live_request(
            case=_case("DEV-RESTRICTED-BLOCK"),
            context=_context(session_sensitivity="RESTRICTED"),
            config=_config(),
            data_policy=OutboundDataPolicy(max_sensitivity="CONFIDENTIAL"),
        )


def test_prepare_live_request_requires_explicit_memory_sensitivity():
    context = _context()
    memory = tuple({k: v for k, v in context.memory[0].items() if k != "sensitivity"} for _ in [0])
    unsafe = ContextBundle(
        project_scope=context.project_scope,
        valid_at=context.valid_at,
        recorded_at=context.recorded_at,
        memory=memory,
        evidence_refs=context.evidence_refs,
        session_items=context.session_items,
    )
    with pytest.raises(ProviderLiveBoundaryError, match="lacks explicit sensitivity"):
        prepare_g3c2b0_live_request(
            case=_case("DEV-NO-SENSITIVITY"),
            context=unsafe,
            config=_config(),
            data_policy=OutboundDataPolicy(),
        )


def test_holdout_is_rejected_before_any_http_client_call():
    client = RecordingHTTPClient()
    adapter = ProviderALiveAdapter(
        config=_config(),
        data_policy=OutboundDataPolicy(),
        http_client=client,
        environment={"OPENAI_API_KEY": API_KEY},
    )
    with pytest.raises(ProviderLiveBoundaryError, match="Holdout execution is forbidden"):
        adapter.execute(
            case=_case("HOLD-1", "holdout"),
            context=_context(),
            r2_authority_ref="R2-FUTURE",
        )
    assert client.calls == []


def test_live_execute_requires_explicit_r2_authority_before_http_or_credential():
    client = RecordingHTTPClient()
    adapter = ProviderALiveAdapter(
        config=_config(),
        data_policy=OutboundDataPolicy(),
        http_client=client,
        environment={},
    )
    with pytest.raises(ProviderLiveBoundaryError, match="requires an explicit R2 authority"):
        adapter.execute(case=_case("DEV-NO-R2"), context=_context())
    assert client.calls == []


def test_missing_openai_api_key_fails_before_http_call():
    client = RecordingHTTPClient()
    adapter = ProviderALiveAdapter(
        config=_config(),
        data_policy=OutboundDataPolicy(),
        http_client=client,
        environment={},
    )
    with pytest.raises(ProviderLiveBoundaryError, match="OPENAI_API_KEY"):
        adapter.execute(
            case=_case("DEV-NO-KEY"),
            context=_context(),
            r2_authority_ref="R2-FUTURE",
        )
    assert client.calls == []


def test_mocked_live_execution_records_real_counts_ids_and_payload_digest():
    prepared = prepare_g3c2b0_live_request(
        case=_case("DEV-LIVE-MOCK"),
        context=_context(),
        config=_config(),
        data_policy=OutboundDataPolicy(),
    )
    client = RecordingHTTPClient(responses=[_success_response(prepared.client_request_id)])
    adapter = ProviderALiveAdapter(
        config=_config(),
        data_policy=OutboundDataPolicy(),
        http_client=client,
        environment={"OPENAI_API_KEY": API_KEY},
    )

    trace = adapter.execute(
        case=_case("DEV-LIVE-MOCK"),
        context=_context(),
        r2_authority_ref="R2-FUTURE-FIXTURE",
    )

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["url"] == "https://api.openai.com/v1/responses"
    assert call["headers"]["Authorization"] == f"Bearer {API_KEY}"
    assert call["headers"]["X-Client-Request-Id"] == prepared.client_request_id
    assert trace["external_provider_calls"] == 1
    assert trace["transport_attempt_count"] == 1
    assert trace["provider_request_id"] == "req_fixture_001"
    assert trace["client_request_id"] == prepared.client_request_id
    assert trace["provider_response_id"] == "resp_fixture_001"
    assert trace["provider_reported_model"] == "gpt-5.6-sol"
    assert trace["payload_sha256"] == prepared.payload_sha256
    assert trace["holdout_executed"] is False
    assert trace["oracle_fields_exposed"] is False
    assert trace["tools_enabled"] is False
    assert API_KEY not in json.dumps(trace, sort_keys=True)


def test_model_identity_drift_fails_closed():
    prepared = prepare_g3c2b0_live_request(
        case=_case("DEV-MODEL-DRIFT"),
        context=_context(),
        config=_config(),
        data_policy=OutboundDataPolicy(),
    )
    response = ProviderAHTTPResponse(
        status_code=200,
        request_id="req_fixture_002",
        client_request_id=prepared.client_request_id,
        response_json=_responses_envelope(model="unexpected-model"),
    )
    client = RecordingHTTPClient(responses=[response])
    adapter = ProviderALiveAdapter(
        config=_config(),
        data_policy=OutboundDataPolicy(),
        http_client=client,
        environment={"OPENAI_API_KEY": API_KEY},
    )
    with pytest.raises(ProviderLiveBoundaryError, match="model identity drift"):
        adapter.execute(
            case=_case("DEV-MODEL-DRIFT"),
            context=_context(),
            r2_authority_ref="R2-FUTURE",
        )


def test_missing_provider_request_id_fails_closed():
    prepared = prepare_g3c2b0_live_request(
        case=_case("DEV-REQ-ID"),
        context=_context(),
        config=_config(),
        data_policy=OutboundDataPolicy(),
    )
    response = ProviderAHTTPResponse(
        status_code=200,
        request_id=None,
        client_request_id=prepared.client_request_id,
        response_json=_responses_envelope(),
    )
    client = RecordingHTTPClient(responses=[response])
    adapter = ProviderALiveAdapter(
        config=_config(),
        data_policy=OutboundDataPolicy(),
        http_client=client,
        environment={"OPENAI_API_KEY": API_KEY},
    )
    with pytest.raises(ProviderLiveBoundaryError, match="missing x-request-id"):
        adapter.execute(
            case=_case("DEV-REQ-ID"),
            context=_context(),
            r2_authority_ref="R2-FUTURE",
        )


def test_timeout_error_is_bounded_and_fail_closed():
    client = RecordingHTTPClient(
        responses=[
            ProviderLiveTransportError("timeout-1"),
            ProviderLiveTransportError("timeout-2"),
        ]
    )
    adapter = ProviderALiveAdapter(
        config=_config(max_attempts=2),
        data_policy=OutboundDataPolicy(),
        http_client=client,
        environment={"OPENAI_API_KEY": API_KEY},
    )
    with pytest.raises(ProviderLiveBoundaryError, match="exhausted 2 attempt"):
        adapter.execute(
            case=_case("DEV-TIMEOUT"),
            context=_context(),
            r2_authority_ref="R2-FUTURE",
        )
    assert len(client.calls) == 2


def test_live_receipt_binds_identity_authority_trace_and_payload_digest():
    prepared = prepare_g3c2b0_live_request(
        case=_case("DEV-RECEIPT"),
        context=_context(),
        config=_config(),
        data_policy=OutboundDataPolicy(),
    )
    client = RecordingHTTPClient(responses=[_success_response(prepared.client_request_id)])
    adapter = ProviderALiveAdapter(
        config=_config(),
        data_policy=OutboundDataPolicy(),
        http_client=client,
        environment={"OPENAI_API_KEY": API_KEY},
    )
    trace = adapter.execute(
        case=_case("DEV-RECEIPT"),
        context=_context(),
        r2_authority_ref="R2-FUTURE-FIXTURE",
    )
    receipt = live_provider_trace_receipt(
        traces=(trace,),
        expected_identity=adapter.identity,
        expected_r2_authority_ref="R2-FUTURE-FIXTURE",
    )

    assert receipt["case_count"] == 1
    assert receipt["external_provider_calls"] == 1
    assert receipt["transport_attempt_count"] == 1
    assert receipt["partition_counts"]["holdout"] == 0
    assert receipt["g3_quality_pass_claimed"] is False
    assert receipt["trace_refs"][0]["trace_sha256"] == trace["trace_sha256"]
    assert receipt["trace_refs"][0]["payload_sha256"] == trace["payload_sha256"]
    assert len(receipt["receipt_sha256"]) == 64


def test_live_receipt_rejects_trace_tampering_and_identity_drift():
    prepared = prepare_g3c2b0_live_request(
        case=_case("DEV-TAMPER"),
        context=_context(),
        config=_config(),
        data_policy=OutboundDataPolicy(),
    )
    client = RecordingHTTPClient(responses=[_success_response(prepared.client_request_id)])
    adapter = ProviderALiveAdapter(
        config=_config(),
        data_policy=OutboundDataPolicy(),
        http_client=client,
        environment={"OPENAI_API_KEY": API_KEY},
    )
    trace = adapter.execute(
        case=_case("DEV-TAMPER"),
        context=_context(),
        r2_authority_ref="R2-FUTURE-FIXTURE",
    )
    tampered = dict(trace)
    tampered["payload_sha256"] = "0" * 64

    with pytest.raises(ProviderLiveBoundaryError, match="trace digest mismatch"):
        live_provider_trace_receipt(
            traces=(tampered,),
            expected_identity=adapter.identity,
            expected_r2_authority_ref="R2-FUTURE-FIXTURE",
        )

    drifted = adapter.identity.model_copy(update={"profile_version": "drift"})
    with pytest.raises(ProviderLiveBoundaryError, match="identity drift"):
        live_provider_trace_receipt(
            traces=(trace,),
            expected_identity=drifted,
            expected_r2_authority_ref="R2-FUTURE-FIXTURE",
        )


def test_endpoint_allowlist_rejects_host_path_query_and_insecure_scheme():
    for url in (
        "http://api.openai.com/v1/responses",
        "https://example.com/v1/responses",
        "https://api.openai.com/v1/chat/completions",
        "https://api.openai.com/v1/responses?debug=true",
    ):
        with pytest.raises(ProviderLiveBoundaryError):
            _validate_endpoint(url)


def test_real_http_client_is_blocked_by_ci_no_outbound_guard(monkeypatch):
    monkeypatch.setenv("SOAIACORE_G3C2B0_NO_OUTBOUND", "1")
    client = UrllibProviderAHTTPClient()
    with pytest.raises(ProviderLiveBoundaryError, match="CI no-outbound guard"):
        client.post_json(
            url="https://api.openai.com/v1/responses",
            headers={"X-Client-Request-Id": "fixture"},
            payload={"model": "gpt-5.6-sol"},
            timeout_seconds=1.0,
        )
