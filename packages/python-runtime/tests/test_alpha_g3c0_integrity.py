import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

from soaiacore_runtime.cognitive_loop import EpistemicClass
from soaiacore_runtime.golden_eval import GoldenCase
from soaiacore_runtime.quality_eval import (
    DatasetCaseRef,
    GoldenDatasetManifest,
    HoldoutSeal,
    MetricName,
    MetricStatus,
    QualityObservation,
    aggregate_quality,
    quality_receipt,
    seal_holdout,
    verify_holdout_seal,
)
from soaiacore_runtime.quality_runner import (
    quality_observation_from_trace,
    quality_observations_from_traces,
)


ROOT = Path(__file__).resolve().parents[1]
V02_MANIFEST_PATH = ROOT / "golden" / "soa-alpha-golden-v0.2.json"
V02_SEAL_PATH = ROOT / "golden" / "soa-alpha-golden-v0.2.holdout-seal.json"


def _v02_manifest() -> GoldenDatasetManifest:
    return GoldenDatasetManifest.model_validate(
        json.loads(V02_MANIFEST_PATH.read_text(encoding="utf-8"))
    )


def _v02_seal() -> HoldoutSeal:
    return HoldoutSeal.model_validate(
        json.loads(V02_SEAL_PATH.read_text(encoding="utf-8"))
    )


def _tiny_manifest() -> GoldenDatasetManifest:
    return GoldenDatasetManifest(
        dataset_id="g3c0-tiny",
        dataset_version="0.1",
        cases=(
            DatasetCaseRef(
                golden_case_id="DEV",
                partition="development",
                content_sha256="0" * 64,
            ),
            DatasetCaseRef(
                golden_case_id="VAL",
                partition="validation",
                content_sha256="1" * 64,
            ),
            DatasetCaseRef(
                golden_case_id="HOLD",
                partition="holdout",
                content_sha256="2" * 64,
            ),
        ),
    )


def _perfect_observation(case_id: str, partition: str) -> QualityObservation:
    return QualityObservation(
        golden_case_id=case_id,
        partition=partition,
        temporal_correct=True,
        critical_provenance_claimed=1,
        critical_provenance_correct=1,
        contradictions_expected=1,
        contradictions_predicted=1,
        contradictions_true_positive=1,
        memory_admissions_predicted=1,
        memory_admissions_true_positive=1,
        decision_reconstruction_expected=True,
        decision_reconstruction_correct=True,
        schema_valid=True,
        project_scope_correct=True,
        epistemic_label_correct=True,
    )


def test_v02_is_derived_partition_complete_and_externally_sealed():
    manifest = _v02_manifest()
    seal = _v02_seal()
    assert manifest.dataset_id == "soa-alpha-golden-v0.2"
    assert manifest.dataset_version == "0.2"
    assert len(manifest.cases) == 27
    assert Counter(case.partition for case in manifest.cases) == {
        "development": 9,
        "validation": 9,
        "holdout": 9,
    }
    by_id = {case.golden_case_id: case for case in manifest.cases}
    assert by_id["SOC-MEMADM-013"].partition == "development"
    assert by_id["SOC-MEMADM-014"].partition == "validation"
    assert by_id["SOC-MEMADM-015"].partition == "holdout"
    assert seal.holdout_case_count == 9
    assert seal.holdout_sha256 == (
        "1f3e42cc6f1c66ce4136c89a208426e02d9456296c31054fe6e43ff0a3f4f98c"
    )
    assert verify_holdout_seal(manifest, seal) is True


def test_quality_receipt_requires_exact_case_coverage_partition_and_external_seal():
    manifest = _tiny_manifest()
    seal = seal_holdout(manifest)
    observations = (
        _perfect_observation("DEV", "development"),
        _perfect_observation("VAL", "validation"),
        _perfect_observation("HOLD", "holdout"),
    )

    receipt = quality_receipt(
        manifest=manifest,
        expected_holdout_seal=seal,
        observations=observations,
    )
    assert receipt["aggregation"]["g3_quality_pass"] is True

    with pytest.raises(ValueError, match="observation coverage mismatch"):
        quality_receipt(
            manifest=manifest,
            expected_holdout_seal=seal,
            observations=observations[:2],
        )

    mismatched = observations[0].model_copy(update={"partition": "validation"})
    with pytest.raises(ValueError, match="observation partition mismatch"):
        quality_receipt(
            manifest=manifest,
            expected_holdout_seal=seal,
            observations=(mismatched, observations[1], observations[2]),
        )

    bad_seal = seal.model_copy(update={"holdout_sha256": "f" * 64})
    with pytest.raises(ValueError, match="external holdout seal mismatch"):
        quality_receipt(
            manifest=manifest,
            expected_holdout_seal=bad_seal,
            observations=observations,
        )


def test_unmeasured_signals_remain_not_measured_instead_of_passing():
    observations = (
        QualityObservation(
            golden_case_id="DEV",
            partition="development",
            temporal_correct=True,
            project_scope_correct=True,
            epistemic_label_correct=True,
        ),
    )
    aggregate = aggregate_quality(observations)
    by_metric = {item.metric: item for item in aggregate.measurements}
    assert by_metric[MetricName.TEMPORAL_ACCURACY].status is MetricStatus.PASS
    assert by_metric[MetricName.PROVENANCE_PRECISION_CRITICAL].status is MetricStatus.NOT_MEASURED
    assert by_metric[MetricName.CONTRADICTION_RECALL].status is MetricStatus.NOT_MEASURED
    assert by_metric[MetricName.CONTRADICTION_PRECISION].status is MetricStatus.NOT_MEASURED
    assert by_metric[MetricName.MEMORY_ADMISSION_PRECISION].status is MetricStatus.NOT_MEASURED
    assert by_metric[MetricName.DECISION_RECONSTRUCTION].status is MetricStatus.NOT_MEASURED
    assert by_metric[MetricName.SCHEMA_VALIDITY].status is MetricStatus.NOT_MEASURED
    assert aggregate.g3_quality_pass is False


def test_runner_maps_only_objective_trace_signals_to_measurement():
    case = GoldenCase(
        golden_case_id="SOC-MEMADM-SYN",
        project_scope="SOAiaCore",
        question="synthetic memory admission check",
        cutoff_time=datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc),
        expected_epistemic_class=EpistemicClass.CONFIRMED_CONTEXT,
        expected_claims=("synthetic",),
        expected_decision_state="ADMIT",
        contradictions_expected=("C-1",),
        required_provenance=("synthetic:memory",),
        partition="development",
    )
    trace = {
        "project_scope": "SOAiaCore",
        "context_refs": (),
        "output": {
            "epistemic_class": "CONFIRMED_CONTEXT",
            "provenance_refs": ("evidence:synthetic:memory",),
            "evidence_refs": (),
            "material_effect": False,
        },
        "policy": {
            "canonical_write_allowed": False,
            "action": "PROPOSE_CLAIM",
        },
        "quality_signals": {
            "critical_provenance_refs": ["evidence:synthetic:memory"],
            "contradictions_predicted": ["C-1"],
            "memory_admission_decision": "ADMIT",
            "decision_state": "ADMIT",
            "schema_valid": True,
        },
    }
    observation = quality_observation_from_trace(case=case, trace=trace)
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


def test_runner_missing_semantic_signals_stays_fail_closed_and_requires_trace_coverage():
    case = GoldenCase(
        golden_case_id="ONLY",
        project_scope="SOAiaCore",
        question="synthetic",
        cutoff_time=datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc),
        expected_epistemic_class=EpistemicClass.CONFIRMED_CONTEXT,
        expected_decision_state="ADMIT",
        partition="development",
    )
    trace = {
        "project_scope": "SOAiaCore",
        "context_refs": (),
        "output": {
            "epistemic_class": "CONFIRMED_CONTEXT",
            "provenance_refs": (),
            "evidence_refs": (),
            "material_effect": False,
        },
        "policy": {
            "canonical_write_allowed": False,
            "action": "KEEP_EPHEMERAL",
        },
    }
    observation = quality_observation_from_trace(case=case, trace=trace)
    assert observation.temporal_correct is True
    assert observation.project_scope_correct is True
    assert observation.epistemic_label_correct is True
    assert observation.critical_provenance_claimed is None
    assert observation.contradictions_expected is None
    assert observation.memory_admissions_predicted is None
    assert observation.decision_reconstruction_expected is None
    assert observation.schema_valid is None

    with pytest.raises(ValueError, match="trace coverage mismatch"):
        quality_observations_from_traces(cases=(case,), traces_by_case_id={})
