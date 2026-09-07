import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from soaiacore_runtime.quality_eval import (
    GoldenDatasetManifest,
    MetricName,
    MetricStatus,
    QualityObservation,
    aggregate_quality,
    quality_receipt,
    seal_holdout,
    verify_holdout_seal,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "golden" / "soa-alpha-g3a-conformance-v0.1.json"


def _manifest() -> GoldenDatasetManifest:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return GoldenDatasetManifest.model_validate(
        {
            "dataset_id": raw["dataset_id"],
            "dataset_version": raw["dataset_version"],
            "cases": raw["cases"],
        }
    )


def _observation(case_id: str, partition: str, *, perfect: bool = True) -> QualityObservation:
    return QualityObservation(
        golden_case_id=case_id,
        partition=partition,
        temporal_correct=perfect,
        critical_provenance_claimed=1,
        critical_provenance_correct=1 if perfect else 0,
        contradictions_expected=1,
        contradictions_predicted=1,
        contradictions_true_positive=1 if perfect else 0,
        memory_admissions_predicted=1,
        memory_admissions_true_positive=1 if perfect else 0,
        decision_reconstruction_expected=True,
        decision_reconstruction_correct=perfect,
        schema_valid=perfect,
        project_scope_correct=perfect,
        epistemic_label_correct=perfect,
    )


def test_manifest_is_partition_complete_and_holdout_seal_is_deterministic():
    manifest = _manifest()
    first = seal_holdout(manifest)
    second = seal_holdout(manifest)
    assert first == second
    assert first.holdout_case_count == 1
    assert len(first.holdout_sha256) == 64
    assert verify_holdout_seal(manifest, first) is True


def test_manifest_rejects_missing_partition_and_duplicate_case_id():
    valid = _manifest()
    with pytest.raises(ValidationError, match="partition coverage invalid"):
        GoldenDatasetManifest(
            dataset_id="bad",
            dataset_version="0.1",
            cases=tuple(case for case in valid.cases if case.partition != "holdout"),
        )
    duplicate = valid.cases[0]
    with pytest.raises(ValidationError, match="duplicate golden_case_id"):
        GoldenDatasetManifest(
            dataset_id="bad-dup",
            dataset_version="0.1",
            cases=(duplicate, duplicate, valid.cases[2]),
        )


def test_all_normative_metrics_emit_denominators_rates_and_pass_when_perfect():
    observations = (
        _observation("G3A-SYN-DEV-001", "development"),
        _observation("G3A-SYN-VAL-001", "validation"),
        _observation("G3A-SYN-HOLD-001", "holdout"),
    )
    aggregate = aggregate_quality(observations)
    assert aggregate.case_count == 3
    assert len(aggregate.measurements) == 9
    assert aggregate.all_thresholds_measured is True
    assert aggregate.g3_quality_pass is True
    assert aggregate.failures == ()
    assert {measurement.metric for measurement in aggregate.measurements} == set(MetricName)
    for measurement in aggregate.measurements:
        assert measurement.denominator > 0
        assert measurement.rate == 1.0
        assert measurement.status is MetricStatus.PASS


def test_zero_denominator_is_not_measured_and_can_never_claim_g3_pass():
    observation = QualityObservation(
        golden_case_id="G3A-SYN-DEV-001",
        partition="development",
        temporal_correct=True,
        critical_provenance_claimed=0,
        critical_provenance_correct=0,
        contradictions_expected=0,
        contradictions_predicted=0,
        contradictions_true_positive=0,
        memory_admissions_predicted=0,
        memory_admissions_true_positive=0,
        decision_reconstruction_expected=False,
        decision_reconstruction_correct=False,
        schema_valid=True,
        project_scope_correct=True,
        epistemic_label_correct=True,
    )
    aggregate = aggregate_quality((observation,))
    by_metric = {item.metric: item for item in aggregate.measurements}
    assert by_metric[MetricName.CONTRADICTION_RECALL].status is MetricStatus.NOT_MEASURED
    assert by_metric[MetricName.MEMORY_ADMISSION_PRECISION].status is MetricStatus.NOT_MEASURED
    assert by_metric[MetricName.DECISION_RECONSTRUCTION].status is MetricStatus.NOT_MEASURED
    assert aggregate.all_thresholds_measured is False
    assert aggregate.g3_quality_pass is False
    assert any(failure.endswith("_NOT_MEASURED") for failure in aggregate.failures)


def test_below_threshold_measurements_emit_stable_failure_taxonomy():
    aggregate = aggregate_quality(
        (
            _observation("G3A-SYN-DEV-001", "development", perfect=False),
            _observation("G3A-SYN-VAL-001", "validation", perfect=True),
            _observation("G3A-SYN-HOLD-001", "holdout", perfect=True),
        )
    )
    assert aggregate.g3_quality_pass is False
    assert "G3_TEMPORAL_ACCURACY_BELOW_THRESHOLD" in aggregate.failures
    assert "G3_CONTRADICTION_RECALL_BELOW_THRESHOLD" in aggregate.failures
    assert "G3_SCHEMA_VALIDITY_BELOW_THRESHOLD" in aggregate.failures


def test_quality_receipt_is_reproducible_and_contains_no_payload():
    manifest = _manifest()
    observations = (
        _observation("G3A-SYN-DEV-001", "development"),
        _observation("G3A-SYN-VAL-001", "validation"),
        _observation("G3A-SYN-HOLD-001", "holdout"),
    )
    first = quality_receipt(manifest=manifest, observations=observations)
    second = quality_receipt(manifest=manifest, observations=observations)
    assert first == second
    assert len(first["receipt_sha256"]) == 64
    assert first["aggregation"]["g3_quality_pass"] is True
    assert first["semantic_judge_used"] is False
    assert first["external_provider_calls"] == 0
    serialized = json.dumps(first, sort_keys=True).lower()
    assert "synthetic-development-case" not in serialized
    assert "synthetic-validation-case" not in serialized
    assert "synthetic-holdout-case" not in serialized


def test_quality_receipt_rejects_observation_outside_manifest():
    manifest = _manifest()
    with pytest.raises(ValueError, match="observations not present in manifest"):
        quality_receipt(
            manifest=manifest,
            observations=(_observation("UNKNOWN", "development"),),
        )
