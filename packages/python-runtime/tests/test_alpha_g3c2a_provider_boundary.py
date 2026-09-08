from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

from soaiacore_runtime.cognitive_loop import (
    ContextBundle,
    EpistemicClass,
    OutputDisposition,
)
from soaiacore_runtime.golden_eval import GoldenCase
from soaiacore_runtime.provider_eval import (
    ProviderAAdapter,
    ProviderAConfig,
    ProviderExecutionError,
    ProviderTransportError,
    execute_g3c2a_provider_case,
    execute_g3c2a_provider_dataset,
    provider_trace_receipt,
)
from soaiacore_runtime.quality_runner import quality_observation_from_trace


NOW = datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc)
API_KEY = "runtime-secret-not-a-real-key"


def _config(*, max_attempts: int = 2) -> ProviderAConfig:
    return ProviderAConfig(
        model_id="provider-a-fixture-model",
        profile_version="g3c2a-profile/0.1",
        adapter_version="provider-a-boundary/0.1",
        max_attempts=max_attempts,
    )


def _context(scope: str = "SOAiaCore") -> ContextBundle:
    return ContextBundle(
        project_scope=scope,
        valid_at=NOW,
        recorded_at=NOW,
        memory=(
            {
                "memory_id": "M-DEV-1",
                "project_scope": scope,
                "claim": "Synthetic governed context only.",
            },
        ),
        evidence_refs=("synthetic:dev",),
        session_items=(),
    )


def _case(
    case_id: str,
    partition: str = "development",
    *,
    question: str = "What is the governed state?",
) -> GoldenCase:
    return GoldenCase(
        golden_case_id=case_id,
        project_scope="SOAiaCore",
        question=question,
        cutoff_time=NOW,
        allowed_evidence_refs=("synthetic:dev",),
        expected_epistemic_class=EpistemicClass.CONFIRMED_CONTEXT,
        expected_claims=("governed state confirmed",),
        expected_decision_state="ADMIT",
        contradictions_expected=("C-1",),
        required_provenance=("synthetic:dev",),
        partition=partition,
    )


def _good_response() -> dict[str, Any]:
    return {
        "content": "The governed state is confirmed by the supplied context.",
        "epistemic_class": EpistemicClass.CONFIRMED_CONTEXT.value,
        "disposition": OutputDisposition.CLAIM_PROPOSAL.value,
        "claims": ["governed state confirmed"],
        "evidence_refs": ["synthetic:dev"],
        "provenance_refs": ["evidence:synthetic:dev"],
        "contradictions_predicted": ["C-1"],
        "memory_admission_decision": "ADMIT",
        "decision_state": "ADMIT",
        "tool_name": None,
        "material_effect": False,
    }


class FakeTransport:
    def __init__(
        self,
        *,
        responses: list[dict[str, Any] | Exception] | None = None,
        external: bool = False,
    ) -> None:
        self._external = external
        self.responses = list(responses or [_good_response()])
        self.payloads: list[dict[str, Any]] = []
        self.credentials: list[str] = []
        self.call_count = 0

    @property
    def external(self) -> bool:
        return self._external

    def send(self, *, payload: dict[str, Any], credential: str) -> dict[str, Any]:
        self.call_count += 1
        self.payloads.append(payload)
        self.credentials.append(credential)
        if not self.responses:
            raise AssertionError("fake transport exhausted")
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def _adapter(
    transport: FakeTransport,
    *,
    environment: dict[str, str] | None = None,
    max_attempts: int = 2,
) -> ProviderAAdapter:
    return ProviderAAdapter(
        config=_config(max_attempts=max_attempts),
        transport=transport,
        environment=environment if environment is not None else {"OPENAI_API_KEY": API_KEY},
    )


def test_provider_a_request_excludes_oracle_and_secret_from_trace():
    sentinel = "ORACLE_SENTINEL_MUST_NOT_REACH_PROVIDER"
    case = GoldenCase(
        golden_case_id="DEV-PROVIDER-ORACLE-SEPARATION",
        project_scope="SOAiaCore",
        question="Answer only from supplied runtime context.",
        cutoff_time=NOW,
        allowed_evidence_refs=("synthetic:dev",),
        forbidden_future_refs=(sentinel,),
        expected_epistemic_class=EpistemicClass.CONFIRMED_CONTEXT,
        expected_claims=(sentinel,),
        expected_decision_state=sentinel,
        contradictions_expected=(sentinel,),
        required_provenance=(sentinel,),
        forbidden_tool_classes=(sentinel,),
        notes=sentinel,
        partition="development",
    )
    transport = FakeTransport()
    adapter = _adapter(transport)

    trace = execute_g3c2a_provider_case(case=case, context=_context(), adapter=adapter)

    assert transport.call_count == 1
    assert transport.credentials == [API_KEY]
    wire = json.dumps(transport.payloads[0], sort_keys=True)
    serialized_trace = json.dumps(trace, sort_keys=True)
    assert sentinel not in wire
    assert "expected_claims" not in wire
    assert "expected_decision_state" not in wire
    assert "contradictions_expected" not in wire
    assert "required_provenance" not in wire
    assert "forbidden_future_refs" not in wire
    assert API_KEY not in wire
    assert API_KEY not in serialized_trace
    assert trace["external_provider_calls"] == 0
    assert trace["oracle_fields_exposed"] is False
    assert trace["holdout_executed"] is False
    assert trace["tools_enabled"] is False


def test_g3c2a_rejects_holdout_before_transport_invocation():
    transport = FakeTransport()
    adapter = _adapter(transport)
    with pytest.raises(ProviderExecutionError, match="Holdout execution is forbidden"):
        execute_g3c2a_provider_case(
            case=_case("HOLD-PROVIDER", "holdout"),
            context=_context(),
            adapter=adapter,
        )
    assert transport.call_count == 0


def test_g3c2a_rejects_external_transport_before_outbound_call():
    transport = FakeTransport(external=True)
    adapter = _adapter(transport)
    with pytest.raises(ProviderExecutionError, match="forbids external provider transport"):
        execute_g3c2a_provider_case(
            case=_case("DEV-EXTERNAL-BLOCK"),
            context=_context(),
            adapter=adapter,
        )
    assert transport.call_count == 0


def test_provider_credential_must_come_from_runtime_env():
    transport = FakeTransport()
    adapter = _adapter(transport, environment={})
    with pytest.raises(ProviderExecutionError, match="credential missing from runtime env"):
        execute_g3c2a_provider_case(
            case=_case("DEV-NO-CREDENTIAL"),
            context=_context(),
            adapter=adapter,
        )
    assert transport.call_count == 0


def test_retry_is_bounded_and_receipted_without_external_calls():
    transport = FakeTransport(
        responses=[ProviderTransportError("temporary"), _good_response()]
    )
    adapter = _adapter(transport, max_attempts=2)

    trace = execute_g3c2a_provider_case(
        case=_case("DEV-RETRY"),
        context=_context(),
        adapter=adapter,
    )

    assert transport.call_count == 2
    assert trace["transport_attempt_count"] == 2
    assert trace["candidate_call_count"] == 1
    assert trace["external_provider_calls"] == 0


def test_retry_exhaustion_fails_closed():
    transport = FakeTransport(
        responses=[ProviderTransportError("one"), ProviderTransportError("two")]
    )
    adapter = _adapter(transport, max_attempts=2)
    with pytest.raises(ProviderExecutionError, match="exhausted 2 attempt"):
        execute_g3c2a_provider_case(
            case=_case("DEV-RETRY-FAIL"),
            context=_context(),
            adapter=adapter,
        )
    assert transport.call_count == 2


def test_malformed_structured_output_fails_closed():
    transport = FakeTransport(responses=[{"content": "missing required enums"}])
    adapter = _adapter(transport)
    with pytest.raises(ProviderExecutionError, match="structured output validation failed"):
        execute_g3c2a_provider_case(
            case=_case("DEV-MALFORMED"),
            context=_context(),
            adapter=adapter,
        )


def test_tool_or_material_effect_request_is_rejected():
    response = _good_response()
    response["tool_name"] = "dangerous_tool"
    response["material_effect"] = True
    transport = FakeTransport(responses=[response])
    adapter = _adapter(transport)
    with pytest.raises(ProviderExecutionError, match="forbidden tool/material effect"):
        execute_g3c2a_provider_case(
            case=_case("DEV-TOOL-BLOCK"),
            context=_context(),
            adapter=adapter,
        )


def test_provider_trace_produces_objective_quality_signals():
    case = _case("DEV-QUALITY")
    transport = FakeTransport()
    adapter = _adapter(transport)

    trace = execute_g3c2a_provider_case(case=case, context=_context(), adapter=adapter)
    observation = quality_observation_from_trace(case=case, trace=trace)

    assert trace["candidate"]["provider"] == "openai"
    assert trace["candidate"]["execution_mode"] == "REPLAY"
    assert observation.temporal_correct is True
    assert observation.critical_provenance_claimed == 1
    assert observation.critical_provenance_correct == 1
    assert observation.contradictions_expected == 1
    assert observation.contradictions_predicted == 1
    assert observation.contradictions_true_positive == 1
    assert observation.memory_admissions_predicted == 1
    assert observation.memory_admissions_true_positive == 1
    assert observation.decision_reconstruction_expected is True
    assert observation.decision_reconstruction_correct is True
    assert observation.schema_valid is True
    assert observation.project_scope_correct is True
    assert observation.epistemic_label_correct is True


def test_dataset_coverage_and_receipt_bind_identity_and_trace_digests():
    cases = (
        _case("DEV-PROVIDER-1", "development"),
        _case("VAL-PROVIDER-1", "validation"),
    )
    contexts = {case.golden_case_id: _context() for case in cases}
    transport = FakeTransport(responses=[_good_response(), _good_response()])
    adapter = _adapter(transport)

    traces = execute_g3c2a_provider_dataset(
        cases=cases,
        contexts_by_case_id=contexts,
        adapter=adapter,
    )
    receipt = provider_trace_receipt(traces=traces, expected_identity=adapter.identity)

    assert transport.call_count == 2
    assert receipt["case_count"] == 2
    assert receipt["partition_counts"] == {
        "development": 1,
        "validation": 1,
        "holdout": 0,
    }
    assert receipt["candidate_call_count"] == 2
    assert receipt["external_provider_calls"] == 0
    assert receipt["holdout_executed"] is False
    assert receipt["g3_quality_pass_claimed"] is False
    assert len(receipt["trace_refs"]) == 2
    assert len(receipt["receipt_sha256"]) == 64


def test_dataset_rejects_incomplete_context_coverage():
    cases = (
        _case("DEV-PROVIDER-1", "development"),
        _case("VAL-PROVIDER-1", "validation"),
    )
    transport = FakeTransport()
    adapter = _adapter(transport)
    with pytest.raises(ProviderExecutionError, match="context coverage mismatch"):
        execute_g3c2a_provider_dataset(
            cases=cases,
            contexts_by_case_id={"DEV-PROVIDER-1": _context()},
            adapter=adapter,
        )
    assert transport.call_count == 0


def test_provider_receipt_rejects_trace_tampering():
    transport = FakeTransport()
    adapter = _adapter(transport)
    trace = execute_g3c2a_provider_case(
        case=_case("DEV-PROVIDER-TAMPER"),
        context=_context(),
        adapter=adapter,
    )
    tampered = dict(trace)
    tampered["output"] = {**trace["output"], "content": "tampered"}

    with pytest.raises(ProviderExecutionError, match="trace digest mismatch"):
        provider_trace_receipt(traces=(tampered,), expected_identity=adapter.identity)
