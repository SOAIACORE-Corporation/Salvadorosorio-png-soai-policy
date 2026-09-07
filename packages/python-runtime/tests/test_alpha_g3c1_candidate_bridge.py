from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from soaiacore_runtime.candidate_eval import (
    CandidateIdentity,
    CandidateStructuredOutput,
    candidate_trace_receipt,
    execute_g3c1_candidate_case,
    execute_g3c1_candidate_dataset,
)
from soaiacore_runtime.cognitive_loop import (
    CognitiveInvocationRequest,
    ContextBundle,
    EpistemicClass,
    OutputDisposition,
)
from soaiacore_runtime.golden_eval import GoldenCase
from soaiacore_runtime.quality_eval import GoldenDatasetManifest
from soaiacore_runtime.quality_runner import quality_observation_from_trace


ROOT = Path(__file__).resolve().parents[1]
V02_MANIFEST_PATH = ROOT / "golden" / "soa-alpha-golden-v0.2.json"
NOW = datetime(2026, 9, 7, 18, 0, tzinfo=timezone.utc)


def _identity(*, mode: str = "SYNTHETIC") -> CandidateIdentity:
    return CandidateIdentity(
        provider="SYNTHETIC",
        model_id="g3c1-fixture-model",
        profile_version="g3c1-profile/0.1",
        adapter_version="candidate-bridge/0.1",
        execution_mode=mode,
    )


def _context(scope: str = "SOAiaCore") -> ContextBundle:
    return ContextBundle(
        project_scope=scope,
        valid_at=NOW,
        recorded_at=NOW,
        memory=(),
        evidence_refs=("synthetic:dev",),
        session_items=(),
    )


def _case(
    case_id: str,
    partition: str,
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
        expected_claims=("expected claim",),
        expected_decision_state="ADMIT",
        contradictions_expected=("C-1",),
        required_provenance=("synthetic:dev",),
        partition=partition,
    )


class RecordingAdapter:
    def __init__(
        self,
        *,
        identity: CandidateIdentity | None = None,
        result: CandidateStructuredOutput | None = None,
    ) -> None:
        self._identity = identity or _identity()
        self._result = result or CandidateStructuredOutput(
            content="The governed state is confirmed by the supplied context.",
            epistemic_class=EpistemicClass.CONFIRMED_CONTEXT,
            disposition=OutputDisposition.CLAIM_PROPOSAL,
            claims=("governed state confirmed",),
            evidence_refs=("synthetic:dev",),
            provenance_refs=("evidence:synthetic:dev",),
            contradictions_predicted=("C-1",),
            memory_admission_decision="ADMIT",
            decision_state="ADMIT",
        )
        self.requests: list[CognitiveInvocationRequest] = []
        self.call_count = 0

    @property
    def identity(self) -> CandidateIdentity:
        return self._identity

    def invoke(
        self,
        request: CognitiveInvocationRequest,
        context: ContextBundle,
    ) -> CandidateStructuredOutput:
        assert context.project_scope == "SOAiaCore"
        self.requests.append(request)
        self.call_count += 1
        return self._result


def test_candidate_request_excludes_golden_oracle_fields():
    sentinel = "ORACLE_SENTINEL_MUST_NOT_REACH_CANDIDATE"
    case = GoldenCase(
        golden_case_id="DEV-ORACLE-SEPARATION",
        project_scope="SOAiaCore",
        question="Answer from the supplied runtime context only.",
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
    adapter = RecordingAdapter()

    trace = execute_g3c1_candidate_case(case=case, context=_context(), adapter=adapter)

    assert adapter.call_count == 1
    serialized = json.dumps(adapter.requests[0].model_dump(mode="json"), sort_keys=True)
    assert sentinel not in serialized
    assert "expected_claims" not in serialized
    assert "expected_decision_state" not in serialized
    assert "contradictions_expected" not in serialized
    assert "required_provenance" not in serialized
    assert "forbidden_future_refs" not in serialized
    assert trace["oracle_fields_exposed"] is False
    assert trace["external_provider_calls"] == 0
    assert trace["holdout_executed"] is False


def test_g3c1_rejects_holdout_before_candidate_invocation():
    adapter = RecordingAdapter()
    with pytest.raises(ValueError, match="holdout execution is forbidden"):
        execute_g3c1_candidate_case(
            case=_case("HOLD-1", "holdout"),
            context=_context(),
            adapter=adapter,
        )
    assert adapter.call_count == 0


def test_g3c1_rejects_non_synthetic_candidate_before_invocation():
    adapter = RecordingAdapter(identity=_identity(mode="LIVE"))
    with pytest.raises(ValueError, match="SYNTHETIC candidate execution only"):
        execute_g3c1_candidate_case(
            case=_case("DEV-LIVE", "development"),
            context=_context(),
            adapter=adapter,
        )
    assert adapter.call_count == 0


def test_candidate_trace_maps_structured_signals_after_candidate_returns():
    case = _case("DEV-SIGNALS", "development")
    adapter = RecordingAdapter()

    trace = execute_g3c1_candidate_case(case=case, context=_context(), adapter=adapter)
    observation = quality_observation_from_trace(case=case, trace=trace)

    assert trace["candidate"] == _identity().model_dump(mode="json")
    assert trace["quality_signals"] == {
        "critical_provenance_refs": ["evidence:synthetic:dev"],
        "contradictions_predicted": ["C-1"],
        "memory_admission_decision": "ADMIT",
        "decision_state": "ADMIT",
        "schema_valid": True,
    }
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


def test_dataset_execution_is_exact_dev_validation_only_and_receipt_binds_identity():
    cases = (
        _case("DEV-1", "development"),
        _case("VAL-1", "validation"),
    )
    contexts = {case.golden_case_id: _context() for case in cases}
    adapter = RecordingAdapter()

    traces = execute_g3c1_candidate_dataset(
        cases=cases,
        contexts_by_case_id=contexts,
        adapter=adapter,
    )
    receipt = candidate_trace_receipt(traces=traces, expected_identity=adapter.identity)

    assert adapter.call_count == 2
    assert receipt["case_count"] == 2
    assert receipt["partition_counts"] == {
        "development": 1,
        "validation": 1,
        "holdout": 0,
    }
    assert receipt["candidate_call_count"] == 2
    assert receipt["external_provider_calls"] == 0
    assert receipt["oracle_fields_exposed"] is False
    assert receipt["holdout_executed"] is False
    assert receipt["structured_quality_signals"] is True
    assert receipt["g3_quality_pass_claimed"] is False
    assert len(receipt["receipt_sha256"]) == 64


def test_dataset_execution_rejects_incomplete_context_coverage():
    cases = (
        _case("DEV-1", "development"),
        _case("VAL-1", "validation"),
    )
    adapter = RecordingAdapter()
    with pytest.raises(ValueError, match="context coverage mismatch"):
        execute_g3c1_candidate_dataset(
            cases=cases,
            contexts_by_case_id={"DEV-1": _context()},
            adapter=adapter,
        )
    assert adapter.call_count == 0


def test_public_v02_commitment_exposes_partition_index_not_payload():
    raw = json.loads(V02_MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest = GoldenDatasetManifest.model_validate(raw)

    assert len(manifest.cases) == 27
    assert sum(case.partition == "development" for case in manifest.cases) == 9
    assert sum(case.partition == "validation" for case in manifest.cases) == 9
    assert sum(case.partition == "holdout" for case in manifest.cases) == 9
    assert all(
        set(item) == {"golden_case_id", "partition", "content_sha256"}
        for item in raw["cases"]
    )
    assert not any("question" in item or "expected_claims" in item for item in raw["cases"])
