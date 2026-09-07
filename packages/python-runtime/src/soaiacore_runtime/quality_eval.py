from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .hashing import sha256_json


Partition = Literal["development", "validation", "holdout"]


class MetricName(StrEnum):
    TEMPORAL_ACCURACY = "temporal_accuracy"
    PROVENANCE_PRECISION_CRITICAL = "provenance_precision_critical"
    CONTRADICTION_RECALL = "contradiction_recall"
    CONTRADICTION_PRECISION = "contradiction_precision"
    MEMORY_ADMISSION_PRECISION = "memory_admission_precision"
    DECISION_RECONSTRUCTION = "decision_reconstruction"
    SCHEMA_VALIDITY = "schema_validity"
    PROJECT_SCOPE_ACCURACY = "project_scope_accuracy"
    EPISTEMIC_LABEL_ACCURACY = "epistemic_label_accuracy"


class MetricStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_MEASURED = "NOT_MEASURED"


ALPHA_THRESHOLDS: dict[MetricName, float] = {
    MetricName.TEMPORAL_ACCURACY: 0.98,
    MetricName.PROVENANCE_PRECISION_CRITICAL: 1.00,
    MetricName.CONTRADICTION_RECALL: 0.90,
    MetricName.CONTRADICTION_PRECISION: 0.95,
    MetricName.MEMORY_ADMISSION_PRECISION: 0.95,
    MetricName.DECISION_RECONSTRUCTION: 0.95,
    MetricName.SCHEMA_VALIDITY: 0.99,
    MetricName.PROJECT_SCOPE_ACCURACY: 0.995,
    MetricName.EPISTEMIC_LABEL_ACCURACY: 0.95,
}


FAILURE_TAXONOMY: dict[MetricName, str] = {
    MetricName.TEMPORAL_ACCURACY: "G3_TEMPORAL_ACCURACY_BELOW_THRESHOLD",
    MetricName.PROVENANCE_PRECISION_CRITICAL: "G3_CRITICAL_PROVENANCE_BELOW_THRESHOLD",
    MetricName.CONTRADICTION_RECALL: "G3_CONTRADICTION_RECALL_BELOW_THRESHOLD",
    MetricName.CONTRADICTION_PRECISION: "G3_CONTRADICTION_PRECISION_BELOW_THRESHOLD",
    MetricName.MEMORY_ADMISSION_PRECISION: "G3_MEMORY_ADMISSION_PRECISION_BELOW_THRESHOLD",
    MetricName.DECISION_RECONSTRUCTION: "G3_DECISION_RECONSTRUCTION_BELOW_THRESHOLD",
    MetricName.SCHEMA_VALIDITY: "G3_SCHEMA_VALIDITY_BELOW_THRESHOLD",
    MetricName.PROJECT_SCOPE_ACCURACY: "G3_PROJECT_SCOPE_ACCURACY_BELOW_THRESHOLD",
    MetricName.EPISTEMIC_LABEL_ACCURACY: "G3_EPISTEMIC_LABEL_ACCURACY_BELOW_THRESHOLD",
}


class DatasetCaseRef(BaseModel):
    """Non-payload dataset index entry used for partition and holdout integrity."""

    model_config = ConfigDict(frozen=True)
    golden_case_id: str = Field(min_length=1)
    partition: Partition
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class GoldenDatasetManifest(BaseModel):
    """Partition-aware manifest. Payloads remain outside this contract."""

    model_config = ConfigDict(frozen=True)
    dataset_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    cases: tuple[DatasetCaseRef, ...] = Field(min_length=3)

    @model_validator(mode="after")
    def validate_partition_integrity(self) -> "GoldenDatasetManifest":
        ids = [case.golden_case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate golden_case_id in dataset manifest")
        partitions = {case.partition for case in self.cases}
        required = {"development", "validation", "holdout"}
        if partitions != required:
            missing = sorted(required - partitions)
            extra = sorted(partitions - required)
            raise ValueError(f"partition coverage invalid; missing={missing}, extra={extra}")
        return self


class HoldoutSeal(BaseModel):
    model_config = ConfigDict(frozen=True)
    dataset_id: str
    dataset_version: str
    holdout_case_count: int = Field(ge=1)
    holdout_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def seal_holdout(manifest: GoldenDatasetManifest) -> HoldoutSeal:
    """Create a deterministic seal over holdout identifiers and case digests only."""

    holdout = sorted(
        (
            {
                "golden_case_id": case.golden_case_id,
                "content_sha256": case.content_sha256,
            }
            for case in manifest.cases
            if case.partition == "holdout"
        ),
        key=lambda row: row["golden_case_id"],
    )
    return HoldoutSeal(
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.dataset_version,
        holdout_case_count=len(holdout),
        holdout_sha256=sha256_json(holdout),
    )


def verify_holdout_seal(manifest: GoldenDatasetManifest, seal: HoldoutSeal) -> bool:
    return seal_holdout(manifest) == seal


class QualityObservation(BaseModel):
    """Per-case deterministic measurement inputs; None means not objectively measured."""

    model_config = ConfigDict(frozen=True)
    golden_case_id: str = Field(min_length=1)
    partition: Partition

    temporal_correct: bool | None = None
    critical_provenance_claimed: int | None = Field(default=None, ge=0)
    critical_provenance_correct: int | None = Field(default=None, ge=0)
    contradictions_expected: int | None = Field(default=None, ge=0)
    contradictions_predicted: int | None = Field(default=None, ge=0)
    contradictions_true_positive: int | None = Field(default=None, ge=0)
    memory_admissions_predicted: int | None = Field(default=None, ge=0)
    memory_admissions_true_positive: int | None = Field(default=None, ge=0)
    decision_reconstruction_expected: bool | None = None
    decision_reconstruction_correct: bool | None = None
    schema_valid: bool | None = None
    project_scope_correct: bool | None = None
    epistemic_label_correct: bool | None = None

    @model_validator(mode="after")
    def validate_counts(self) -> "QualityObservation":
        provenance = (self.critical_provenance_claimed, self.critical_provenance_correct)
        if any(value is None for value in provenance) and any(value is not None for value in provenance):
            raise ValueError("critical provenance measurement must be complete or absent")
        if self.critical_provenance_claimed is not None:
            assert self.critical_provenance_correct is not None
            if self.critical_provenance_correct > self.critical_provenance_claimed:
                raise ValueError("critical provenance correct exceeds claimed")

        contradiction = (
            self.contradictions_expected,
            self.contradictions_predicted,
            self.contradictions_true_positive,
        )
        if any(value is None for value in contradiction) and any(value is not None for value in contradiction):
            raise ValueError("contradiction measurement must be complete or absent")
        if self.contradictions_expected is not None:
            assert self.contradictions_predicted is not None
            assert self.contradictions_true_positive is not None
            if self.contradictions_true_positive > self.contradictions_expected:
                raise ValueError("contradiction true positives exceed expected")
            if self.contradictions_true_positive > self.contradictions_predicted:
                raise ValueError("contradiction true positives exceed predicted")

        memory = (self.memory_admissions_predicted, self.memory_admissions_true_positive)
        if any(value is None for value in memory) and any(value is not None for value in memory):
            raise ValueError("memory admission measurement must be complete or absent")
        if self.memory_admissions_predicted is not None:
            assert self.memory_admissions_true_positive is not None
            if self.memory_admissions_true_positive > self.memory_admissions_predicted:
                raise ValueError("memory admission true positives exceed predicted")

        decision = (
            self.decision_reconstruction_expected,
            self.decision_reconstruction_correct,
        )
        if any(value is None for value in decision) and any(value is not None for value in decision):
            raise ValueError("decision reconstruction measurement must be complete or absent")
        if (
            self.decision_reconstruction_expected is False
            and self.decision_reconstruction_correct is True
        ):
            raise ValueError("decision reconstruction cannot be correct when not expected")
        return self


class MetricMeasurement(BaseModel):
    model_config = ConfigDict(frozen=True)
    metric: MetricName
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    rate: float | None
    threshold: float = Field(ge=0.0, le=1.0)
    status: MetricStatus


class QualityAggregation(BaseModel):
    model_config = ConfigDict(frozen=True)
    case_count: int = Field(ge=0)
    measurements: tuple[MetricMeasurement, ...]
    failures: tuple[str, ...]
    all_thresholds_measured: bool
    g3_quality_pass: bool


def _measurement(metric: MetricName, numerator: int, denominator: int) -> MetricMeasurement:
    threshold = ALPHA_THRESHOLDS[metric]
    if denominator == 0:
        return MetricMeasurement(
            metric=metric,
            numerator=numerator,
            denominator=denominator,
            rate=None,
            threshold=threshold,
            status=MetricStatus.NOT_MEASURED,
        )
    rate = numerator / denominator
    return MetricMeasurement(
        metric=metric,
        numerator=numerator,
        denominator=denominator,
        rate=rate,
        threshold=threshold,
        status=MetricStatus.PASS if rate >= threshold else MetricStatus.FAIL,
    )


def _bool_measurement(
    metric: MetricName,
    values: tuple[bool | None, ...],
) -> MetricMeasurement:
    measured = tuple(value for value in values if value is not None)
    return _measurement(metric, sum(bool(value) for value in measured), len(measured))


def aggregate_quality(observations: tuple[QualityObservation, ...]) -> QualityAggregation:
    """Aggregate all normative Alpha G3 rates with explicit measured denominators."""

    case_count = len(observations)
    provenance = tuple(
        obs
        for obs in observations
        if obs.critical_provenance_claimed is not None
    )
    contradictions = tuple(
        obs
        for obs in observations
        if obs.contradictions_expected is not None
    )
    memory = tuple(
        obs
        for obs in observations
        if obs.memory_admissions_predicted is not None
    )
    decisions = tuple(
        obs
        for obs in observations
        if obs.decision_reconstruction_expected is not None
    )

    measurements = (
        _bool_measurement(
            MetricName.TEMPORAL_ACCURACY,
            tuple(obs.temporal_correct for obs in observations),
        ),
        _measurement(
            MetricName.PROVENANCE_PRECISION_CRITICAL,
            sum(int(obs.critical_provenance_correct or 0) for obs in provenance),
            sum(int(obs.critical_provenance_claimed or 0) for obs in provenance),
        ),
        _measurement(
            MetricName.CONTRADICTION_RECALL,
            sum(int(obs.contradictions_true_positive or 0) for obs in contradictions),
            sum(int(obs.contradictions_expected or 0) for obs in contradictions),
        ),
        _measurement(
            MetricName.CONTRADICTION_PRECISION,
            sum(int(obs.contradictions_true_positive or 0) for obs in contradictions),
            sum(int(obs.contradictions_predicted or 0) for obs in contradictions),
        ),
        _measurement(
            MetricName.MEMORY_ADMISSION_PRECISION,
            sum(int(obs.memory_admissions_true_positive or 0) for obs in memory),
            sum(int(obs.memory_admissions_predicted or 0) for obs in memory),
        ),
        _measurement(
            MetricName.DECISION_RECONSTRUCTION,
            sum(
                bool(obs.decision_reconstruction_correct)
                for obs in decisions
                if obs.decision_reconstruction_expected
            ),
            sum(bool(obs.decision_reconstruction_expected) for obs in decisions),
        ),
        _bool_measurement(
            MetricName.SCHEMA_VALIDITY,
            tuple(obs.schema_valid for obs in observations),
        ),
        _bool_measurement(
            MetricName.PROJECT_SCOPE_ACCURACY,
            tuple(obs.project_scope_correct for obs in observations),
        ),
        _bool_measurement(
            MetricName.EPISTEMIC_LABEL_ACCURACY,
            tuple(obs.epistemic_label_correct for obs in observations),
        ),
    )
    failures = tuple(
        FAILURE_TAXONOMY[item.metric]
        if item.status is MetricStatus.FAIL
        else f"G3_{item.metric.value.upper()}_NOT_MEASURED"
        for item in measurements
        if item.status is not MetricStatus.PASS
    )
    all_measured = all(item.status is not MetricStatus.NOT_MEASURED for item in measurements)
    return QualityAggregation(
        case_count=case_count,
        measurements=measurements,
        failures=failures,
        all_thresholds_measured=all_measured,
        g3_quality_pass=all_measured and all(item.status is MetricStatus.PASS for item in measurements),
    )


def quality_receipt(
    *,
    manifest: GoldenDatasetManifest,
    expected_holdout_seal: HoldoutSeal,
    observations: tuple[QualityObservation, ...],
) -> dict[str, Any]:
    """Produce a deterministic fail-closed receipt over the complete sealed dataset."""

    manifest_index = {case.golden_case_id: case for case in manifest.cases}
    manifest_ids = set(manifest_index)
    observation_ids = [obs.golden_case_id for obs in observations]
    if len(observation_ids) != len(set(observation_ids)):
        raise ValueError("duplicate quality observation")

    observed_ids = set(observation_ids)
    missing = sorted(manifest_ids - observed_ids)
    extra = sorted(observed_ids - manifest_ids)
    if missing or extra:
        raise ValueError(
            f"observation coverage mismatch; missing={missing}, extra={extra}"
        )

    partition_mismatches = sorted(
        obs.golden_case_id
        for obs in observations
        if obs.partition != manifest_index[obs.golden_case_id].partition
    )
    if partition_mismatches:
        raise ValueError(
            f"observation partition mismatch: {partition_mismatches}"
        )

    if not verify_holdout_seal(manifest, expected_holdout_seal):
        raise ValueError("external holdout seal mismatch")

    aggregation = aggregate_quality(observations)
    body = {
        "dataset_id": manifest.dataset_id,
        "dataset_version": manifest.dataset_version,
        "manifest_sha256": sha256_json(manifest.model_dump(mode="json")),
        "holdout_seal": expected_holdout_seal.model_dump(mode="json"),
        "thresholds": {metric.value: value for metric, value in ALPHA_THRESHOLDS.items()},
        "aggregation": aggregation.model_dump(mode="json"),
        "observation_partitions": {
            partition: sum(obs.partition == partition for obs in observations)
            for partition in ("development", "validation", "holdout")
        },
        "semantic_judge_used": False,
        "external_provider_calls": 0,
    }
    return {**body, "receipt_sha256": sha256_json(body)}
