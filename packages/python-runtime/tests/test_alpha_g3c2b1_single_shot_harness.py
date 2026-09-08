from __future__ import annotations

import json
from typing import Any

import pytest

from soaiacore_runtime.provider_live import (
    ProviderAHTTPResponse,
    ProviderLiveTransportError,
)
from soaiacore_runtime.provider_live_smoke import (
    SMOKE_CASE_ID,
    SMOKE_MAX_ATTEMPTS,
    SMOKE_OUTBOUND_PERMIT_ENV,
    SMOKE_PARTITION,
    SingleShotSmokeError,
    _config,
    _synthetic_case,
    _synthetic_context,
    main,
    preflight_single_shot_smoke,
    run_single_shot_smoke,
)


API_KEY = "runtime-placeholder-not-a-real-key"


class RecordingHTTPClient:
    def __init__(self, responses: list[ProviderAHTTPResponse | Exception] | None = None) -> None:
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


def _response(*, client_request_id: str) -> ProviderAHTTPResponse:
    body = {
        "content": "Synthetic ALPHA_SMOKE state is READY.",
        "epistemic_class": "CONFIRMED_CONTEXT",
        "disposition": "CLAIM_PROPOSAL",
        "claims": ["Synthetic ALPHA_SMOKE state is READY."],
        "evidence_refs": [],
        "provenance_refs": [],
        "contradictions_predicted": [],
        "memory_admission_decision": "REJECT",
        "decision_state": "READY",
        "tool_name": None,
        "material_effect": False,
    }
    return ProviderAHTTPResponse(
        status_code=200,
        request_id="req_synthetic_smoke_001",
        client_request_id=client_request_id,
        response_json={
            "id": "resp_synthetic_smoke_001",
            "object": "response",
            "status": "completed",
            "model": "gpt-5.6-sol",
            "output": [
                {
                    "type": "message",
                    "id": "msg_synthetic_smoke_001",
                    "status": "completed",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(body, sort_keys=True),
                        }
                    ],
                }
            ],
        },
    )


def _environment() -> dict[str, str]:
    return {
        "OPENAI_API_KEY": API_KEY,
        SMOKE_OUTBOUND_PERMIT_ENV: "1",
    }


def test_smoke_input_is_fixed_public_development_only():
    case = _synthetic_case()
    context = _synthetic_context()
    config = _config()

    assert case.golden_case_id == SMOKE_CASE_ID
    assert case.partition == SMOKE_PARTITION == "development"
    assert context.project_scope == case.project_scope == "SOAiaCore"
    assert all(row["sensitivity"] == "PUBLIC" for row in context.memory)
    assert context.session_items == ()
    assert config.max_attempts == SMOKE_MAX_ATTEMPTS == 1
    assert config.model_id == "gpt-5.6-sol"
    assert config.execution_mode == "LIVE"


def test_preflight_reads_no_credential_and_executes_no_outbound():
    preflight = preflight_single_shot_smoke()
    serialized = json.dumps(preflight, sort_keys=True)

    assert preflight["golden_case_id"] == SMOKE_CASE_ID
    assert preflight["partition"] == "development"
    assert preflight["synthetic_only"] is True
    assert preflight["sensitivity"] == "PUBLIC"
    assert preflight["single_shot"] is True
    assert preflight["max_attempts"] == 1
    assert preflight["full_dataset_evaluation"] is False
    assert preflight["holdout_allowed"] is False
    assert preflight["g3_quality_pass_claimed"] is False
    assert preflight["external_provider_calls"] == 0
    assert preflight["credential_read"] is False
    assert preflight["outbound_executed"] is False
    assert len(preflight["payload_sha256"]) == 64
    assert len(preflight["preflight_sha256"]) == 64
    assert API_KEY not in serialized


def test_execute_requires_exact_r2_authority_before_any_http_call():
    client = RecordingHTTPClient()
    with pytest.raises(SingleShotSmokeError, match="exact R2 authority ref"):
        run_single_shot_smoke(
            r2_authority_ref="",
            http_client=client,
            environment=_environment(),
        )
    assert client.calls == []


def test_execute_requires_separate_outbound_permit_before_any_http_call():
    client = RecordingHTTPClient()
    with pytest.raises(SingleShotSmokeError, match=SMOKE_OUTBOUND_PERMIT_ENV):
        run_single_shot_smoke(
            r2_authority_ref="R2-FUTURE-SMOKE",
            http_client=client,
            environment={"OPENAI_API_KEY": API_KEY},
        )
    assert client.calls == []


def test_single_shot_mock_executes_exactly_once_and_receipts_are_bound():
    preflight = preflight_single_shot_smoke()
    client = RecordingHTTPClient(
        responses=[_response(client_request_id=preflight["client_request_id"])]
    )
    result = run_single_shot_smoke(
        r2_authority_ref="R2-FUTURE-SMOKE",
        http_client=client,
        environment=_environment(),
    )

    assert len(client.calls) == 1
    assert client.calls[0]["url"] == "https://api.openai.com/v1/responses"
    assert client.calls[0]["headers"]["Authorization"] == f"Bearer {API_KEY}"

    trace = result["trace"]
    boundary = result["boundary_receipt"]
    receipt = result["single_shot_receipt"]

    assert trace["golden_case_id"] == SMOKE_CASE_ID
    assert trace["partition"] == "development"
    assert trace["external_provider_calls"] == 1
    assert trace["transport_attempt_count"] == 1
    assert trace["holdout_executed"] is False
    assert trace["oracle_fields_exposed"] is False
    assert trace["tools_enabled"] is False

    assert boundary["case_count"] == 1
    assert boundary["partition_counts"] == {
        "development": 1,
        "validation": 0,
        "holdout": 0,
    }
    assert boundary["external_provider_calls"] == 1
    assert boundary["g3_quality_pass_claimed"] is False

    assert receipt["golden_case_id"] == SMOKE_CASE_ID
    assert receipt["single_shot"] is True
    assert receipt["synthetic_only"] is True
    assert receipt["external_provider_calls"] == 1
    assert receipt["transport_attempt_count"] == 1
    assert receipt["full_dataset_evaluation"] is False
    assert receipt["holdout_allowed"] is False
    assert receipt["holdout_executed"] is False
    assert receipt["g3_quality_pass_claimed"] is False
    assert receipt["provider_trace_sha256"] == trace["trace_sha256"]
    assert receipt["provider_payload_sha256"] == trace["payload_sha256"]
    assert receipt["boundary_receipt_sha256"] == boundary["receipt_sha256"]
    assert len(receipt["receipt_sha256"]) == 64
    assert API_KEY not in json.dumps(result, sort_keys=True)


def test_single_shot_forbids_retry_after_transport_failure():
    client = RecordingHTTPClient(responses=[ProviderLiveTransportError("synthetic timeout")])
    with pytest.raises(Exception, match="exhausted 1 attempt"):
        run_single_shot_smoke(
            r2_authority_ref="R2-FUTURE-SMOKE",
            http_client=client,
            environment=_environment(),
        )
    assert len(client.calls) == 1


def test_cli_preflight_requires_no_key_and_emits_zero_call_receipt(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("SOAIACORE_G3C2B0_NO_OUTBOUND", "1")
    assert main(["preflight"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["golden_case_id"] == SMOKE_CASE_ID
    assert output["external_provider_calls"] == 0
    assert output["credential_read"] is False
    assert output["outbound_executed"] is False


def test_cli_execute_cannot_start_without_outbound_permit(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", API_KEY)
    monkeypatch.setenv(SMOKE_OUTBOUND_PERMIT_ENV, "0")
    monkeypatch.setenv("SOAIACORE_G3C2B0_NO_OUTBOUND", "1")
    with pytest.raises(SingleShotSmokeError, match=SMOKE_OUTBOUND_PERMIT_ENV):
        main(
            [
                "execute",
                "--r2-authority-ref",
                "R2-FUTURE-SMOKE",
                "--receipt-out",
                str(tmp_path / "should-not-exist.json"),
            ]
        )
    assert not (tmp_path / "should-not-exist.json").exists()
