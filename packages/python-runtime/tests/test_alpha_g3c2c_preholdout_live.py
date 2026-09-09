import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from soaiacore_runtime.cognitive_loop import EpistemicClass
from soaiacore_runtime.golden_eval import GoldenCase
from soaiacore_runtime.hashing import sha256_json
from soaiacore_runtime.preholdout_live import (
    BINDING_VERSION,
    PROVIDER_ADAPTER_VERSION,
    PROVIDER_PROFILE_VERSION,
    EvidenceSnippet,
    PreHoldoutBatchStopped,
    PreHoldoutRunnerError,
    PreHoldoutSensitivityBinding,
    PrivatePreHoldoutBundle,
    PrivatePreHoldoutCase,
    canonical_case_sha256,
    execute_preholdout_batch,
    load_sensitivity_binding,
    preflight_batch_plan,
    verify_preholdout_binding,
    verify_private_bundle,
)
from soaiacore_runtime.provider_live import (
    OutboundDataPolicy,
    ProviderAHTTPResponse,
    ProviderALiveAdapter,
    ProviderALiveConfig,
    ProviderLiveTransportError,
)
from soaiacore_runtime.quality_eval import DatasetCaseRef, GoldenDatasetManifest, seal_holdout


ROOT = Path(__file__).resolve().parents[1]
STATIC_BINDING_PATH = ROOT / "golden" / "soa-alpha-golden-v0.2.preholdout-sensitivity.json"
STATIC_MANIFEST_PATH = ROOT / "golden" / "soa-alpha-golden-v0.2.json"


def _case(case_id: str, partition: str, *, expected_label: EpistemicClass = EpistemicClass.CONFIRMED_CONTEXT) -> GoldenCase:
    ref = f"synthetic:{case_id.lower()}"
    return GoldenCase(
        golden_case_id=case_id,
        project_scope="SOAiaCore",
        question=f"What is the governed state for {case_id}?",
        cutoff_time=datetime(2026, 9, 9, 5, 0, tzinfo=timezone.utc),
        allowed_evidence_refs=(ref,),
        forbidden_future_refs=(),
        expected_epistemic_class=expected_label,
        expected_claims=(f"Expected private oracle claim for {case_id}",),
        expected_decision_state="READY",
        contradictions_expected=(),
        required_provenance=(ref,),
        forbidden_tool_classes=("R2", "R3"),
        notes="synthetic fixture",
        partition=partition,
    )


def _tiny_manifest(dev: GoldenCase, val: GoldenCase) -> GoldenDatasetManifest:
    return GoldenDatasetManifest(
        dataset_id="tiny-preholdout",
        dataset_version="0.1",
        cases=(
            DatasetCaseRef(
                golden_case_id=dev.golden_case_id,
                partition="development",
                content_sha256=canonical_case_sha256(dev),
            ),
            DatasetCaseRef(
                golden_case_id=val.golden_case_id,
                partition="validation",
                content_sha256=canonical_case_sha256(val),
            ),
            DatasetCaseRef(
                golden_case_id="HOLD-1",
                partition="holdout",
                content_sha256="f" * 64,
            ),
        ),
    )


def _binding(dev: GoldenCase, val: GoldenCase) -> PreHoldoutSensitivityBinding:
    manifest = _tiny_manifest(dev, val)
    holdout = seal_holdout(manifest)
    body = {
        "binding_version": BINDING_VERSION,
        "case_count": 2,
        "cases": [
            {
                "golden_case_id": dev.golden_case_id,
                "partition": "development",
                "sensitivity": "INTERNAL",
                "content_sha256": canonical_case_sha256(dev),
            },
            {
                "golden_case_id": val.golden_case_id,
                "partition": "validation",
                "sensitivity": "INTERNAL",
                "content_sha256": canonical_case_sha256(val),
            },
        ],
        "dataset_id": manifest.dataset_id,
        "dataset_version": manifest.dataset_version,
        "holdout_sha256": holdout.holdout_sha256,
        "partition_counts": {"development": 1, "validation": 1, "holdout": 0},
        "sensitivity_counts": {"CONFIDENTIAL": 0, "INTERNAL": 2},
        "source_ledger_ref": "SYNTHETIC_PRIVATE_LEDGER",
        "source_manifest_sha256": "a" * 64,
    }
    return PreHoldoutSensitivityBinding.model_validate(
        {**body, "binding_sha256": sha256_json(body)}
    )


def _bundle(dev: GoldenCase, val: GoldenCase) -> PrivatePreHoldoutBundle:
    def payload(case: GoldenCase) -> PrivatePreHoldoutCase:
        ref = case.allowed_evidence_refs[0]
        return PrivatePreHoldoutCase(
            case=case,
            sensitivity="INTERNAL",
            evidence=(
                EvidenceSnippet(
                    ref=ref,
                    text=f"Candidate-visible evidence for {case.golden_case_id}",
                    sensitivity="INTERNAL",
                ),
            ),
        )

    return PrivatePreHoldoutBundle(
        dataset_id="tiny-preholdout",
        dataset_version="0.1",
        sensitivity_scope="INTERNAL",
        cases=(payload(dev), payload(val)),
    )


def _candidate_json(*, alias: str, label: str = "CONFIRMED_CONTEXT", material_effect: bool = False) -> dict:
    return {
        "content": "Candidate answer.",
        "epistemic_class": label,
        "disposition": "CLAIM_PROPOSAL",
        "claims": ["Candidate answer."],
        "evidence_refs": [alias],
        "provenance_refs": [f"evidence:{alias}"],
        "contradictions_predicted": [],
        "memory_admission_decision": None,
        "decision_state": "READY",
        "tool_name": None,
        "material_effect": material_effect,
    }


class RecordingHTTPClient:
    def __init__(self, *, wrong_label_on_call: int | None = None, material_effect_on_call: int | None = None):
        self.calls = []
        self.wrong_label_on_call = wrong_label_on_call
        self.material_effect_on_call = material_effect_on_call

    def post_json(self, *, url, headers, payload, timeout_seconds):
        self.calls.append(payload)
        call = len(self.calls)
        runtime = json.loads(payload["input"][1]["content"][0]["text"])["runtime_context"]
        evidence_alias = runtime["evidence_refs"][0]
        label = "HYPOTHESIS" if call == self.wrong_label_on_call else "CONFIRMED_CONTEXT"
        material = call == self.material_effect_on_call
        output = _candidate_json(alias=evidence_alias, label=label, material_effect=material)
        return ProviderAHTTPResponse(
            status_code=200,
            request_id=f"req-{call}",
            client_request_id=headers["X-Client-Request-Id"],
            response_json={
                "id": f"resp-{call}",
                "status": "completed",
                "model": "gpt-5.6-sol",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(output)}],
                    }
                ],
            },
        )


class FirstTransportFailureHTTPClient(RecordingHTTPClient):
    def post_json(self, *, url, headers, payload, timeout_seconds):
        self.calls.append(payload)
        if len(self.calls) == 1:
            raise ProviderLiveTransportError("synthetic transient")
        runtime = json.loads(payload["input"][1]["content"][0]["text"])["runtime_context"]
        evidence_alias = runtime["evidence_refs"][0]
        output = _candidate_json(alias=evidence_alias)
        return ProviderAHTTPResponse(
            status_code=200,
            request_id="req-2",
            client_request_id=headers["X-Client-Request-Id"],
            response_json={
                "id": "resp-2",
                "status": "completed",
                "model": "gpt-5.6-sol",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(output)}],
                    }
                ],
            },
        )


def _adapter(client, *, max_sensitivity="INTERNAL") -> ProviderALiveAdapter:
    return ProviderALiveAdapter(
        config=ProviderALiveConfig(
            profile_version=PROVIDER_PROFILE_VERSION,
            adapter_version=PROVIDER_ADAPTER_VERSION,
            max_attempts=1,
            max_output_tokens=1024,
        ),
        data_policy=OutboundDataPolicy(max_sensitivity=max_sensitivity),
        http_client=client,
        environment={"OPENAI_API_KEY": "test-only-not-a-real-key"},
    )


def test_static_binding_is_exact_preholdout_18_with_9_internal_9_confidential_and_no_holdout():
    binding = load_sensitivity_binding(STATIC_BINDING_PATH)
    manifest = GoldenDatasetManifest.model_validate(
        json.loads(STATIC_MANIFEST_PATH.read_text(encoding="utf-8"))
    )
    receipt = verify_preholdout_binding(binding=binding, manifest=manifest)

    assert binding.binding_sha256 == "3c839b730981556510ac67bbac58e8afcf4e1432f7fd63a6f6cb244639705bf2"
    assert receipt["case_count"] == 18
    assert receipt["partition_counts"] == {"development": 9, "validation": 9, "holdout": 0}
    assert receipt["sensitivity_counts"] == {"CONFIDENTIAL": 9, "INTERNAL": 9}
    assert all(item.partition != "holdout" for item in binding.cases)


def test_private_bundle_requires_exact_sensitivity_scope_and_case_digest():
    dev = _case("DEV-1", "development")
    val = _case("VAL-1", "validation")
    binding = _binding(dev, val)
    manifest = _tiny_manifest(dev, val)
    bundle = _bundle(dev, val)

    verified = verify_private_bundle(bundle=bundle, binding=binding, manifest=manifest)
    assert verified["case_count"] == 2
    assert verified["private_payload_committed"] is False

    bad_case = dev.model_copy(update={"question": "tampered"})
    bad_bundle = bundle.model_copy(
        update={
            "cases": (
                bundle.cases[0].model_copy(update={"case": bad_case}),
                bundle.cases[1],
            )
        }
    )
    with pytest.raises(PreHoldoutRunnerError, match="payload digest mismatch"):
        verify_private_bundle(bundle=bad_bundle, binding=binding, manifest=manifest)


def test_preflight_binds_exact_main_scope_and_confirmation_without_credential_read():
    dev = _case("DEV-1", "development")
    val = _case("VAL-1", "validation")
    intent = preflight_batch_plan(
        bundle=_bundle(dev, val),
        binding=_binding(dev, val),
        manifest=_tiny_manifest(dev, val),
        expected_main_sha="1" * 40,
        r2_authority_ref="R2-SYNTHETIC",
        one_batch_confirmation="I_UNDERSTAND_NINE_INTERNAL_PREHOLDOUT_CALLS_ONLY",
        current_head_sha="1" * 40,
    )
    assert intent["credential_read"] is False
    assert intent["outbound_executed"] is False
    assert intent["plan"]["holdout"] is False
    assert intent["plan"]["full_dataset"] is False
    assert intent["plan"]["g3_quality_pass_claimed"] is False
    assert len(intent["execution_intent_sha256"]) == 64

    with pytest.raises(PreHoldoutRunnerError, match="confirmation"):
        preflight_batch_plan(
            bundle=_bundle(dev, val),
            binding=_binding(dev, val),
            manifest=_tiny_manifest(dev, val),
            expected_main_sha="1" * 40,
            r2_authority_ref="R2-SYNTHETIC",
            one_batch_confirmation="WRONG",
            current_head_sha="1" * 40,
        )


def test_quality_failure_is_evidence_and_batch_continues_with_oracle_fields_absent_from_wire():
    dev = _case("DEV-1", "development")
    val = _case("VAL-1", "validation")
    client = RecordingHTTPClient(wrong_label_on_call=1)
    receipt = execute_preholdout_batch(
        bundle=_bundle(dev, val),
        binding=_binding(dev, val),
        manifest=_tiny_manifest(dev, val),
        adapter=_adapter(client),
        expected_main_sha="2" * 40,
        r2_authority_ref="R2-SYNTHETIC",
        execution_intent_sha256="3" * 64,
        recorded_at=datetime(2026, 9, 9, 6, 0, tzinfo=timezone.utc),
    )
    assert len(client.calls) == 2
    assert receipt["external_provider_calls"] == 2
    assert receipt["transport_attempt_count"] == 2
    assert receipt["stopped"] is False
    assert receipt["g3_quality_pass_claimed"] is False
    assert receipt["quality_failures_by_case"]["DEV-1"] == ["EPISTEMIC_LABEL_MISMATCH"]

    wire = json.dumps(client.calls[0], sort_keys=True)
    assert "Expected private oracle claim" not in wire
    assert '"expected_decision_state"' not in wire
    assert '"required_provenance"' not in wire


def test_transport_failure_is_amber_no_retry_for_case_and_batch_continues():
    dev = _case("DEV-1", "development")
    val = _case("VAL-1", "validation")
    client = FirstTransportFailureHTTPClient()
    receipt = execute_preholdout_batch(
        bundle=_bundle(dev, val),
        binding=_binding(dev, val),
        manifest=_tiny_manifest(dev, val),
        adapter=_adapter(client),
        expected_main_sha="4" * 40,
        r2_authority_ref="R2-SYNTHETIC",
        execution_intent_sha256="5" * 64,
        recorded_at=datetime(2026, 9, 9, 6, 0, tzinfo=timezone.utc),
    )
    assert len(client.calls) == 2
    assert receipt["external_provider_calls"] == 1
    assert receipt["transport_attempt_count"] == 2
    assert receipt["transport_failure_count"] == 1
    assert receipt["completed_trace_count"] == 1
    assert receipt["stopped"] is False


def test_provider_tool_or_material_effect_is_red_and_stops_before_second_case():
    dev = _case("DEV-1", "development")
    val = _case("VAL-1", "validation")
    client = RecordingHTTPClient(material_effect_on_call=1)

    with pytest.raises(PreHoldoutBatchStopped) as captured:
        execute_preholdout_batch(
            bundle=_bundle(dev, val),
            binding=_binding(dev, val),
            manifest=_tiny_manifest(dev, val),
            adapter=_adapter(client),
            expected_main_sha="6" * 40,
            r2_authority_ref="R2-SYNTHETIC",
            execution_intent_sha256="7" * 64,
            recorded_at=datetime(2026, 9, 9, 6, 0, tzinfo=timezone.utc),
        )

    assert len(client.calls) == 1
    assert captured.value.receipt["stopped"] is True
    assert captured.value.receipt["stop_reason"] == "RED_PROVIDER_BOUNDARY"
    assert captured.value.receipt["g3_quality_pass_claimed"] is False


def test_internal_bundle_cannot_run_under_broader_confidential_policy():
    dev = _case("DEV-1", "development")
    val = _case("VAL-1", "validation")
    with pytest.raises(PreHoldoutRunnerError, match="exactly match"):
        execute_preholdout_batch(
            bundle=_bundle(dev, val),
            binding=_binding(dev, val),
            manifest=_tiny_manifest(dev, val),
            adapter=_adapter(RecordingHTTPClient(), max_sensitivity="CONFIDENTIAL"),
            expected_main_sha="8" * 40,
            r2_authority_ref="R2-SYNTHETIC",
            execution_intent_sha256="9" * 64,
        )
