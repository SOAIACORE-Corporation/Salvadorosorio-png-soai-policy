from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .cognitive_loop import ContextBundle, EpistemicClass
from .golden_eval import GoldenCase, evaluate_golden_case
from .hashing import sha256_json
from .provider_live import (
    OutboundDataPolicy,
    ProviderALiveAdapter,
    ProviderALiveConfig,
    ProviderLiveBoundaryError,
    ProviderLiveTransportError,
    UrllibProviderAHTTPClient,
    live_provider_trace_receipt,
)
from .quality_eval import GoldenDatasetManifest, aggregate_quality
from .quality_runner import quality_observation_from_trace


PreHoldoutSensitivity = Literal["INTERNAL", "CONFIDENTIAL"]
PreHoldoutPartition = Literal["development", "validation"]

BINDING_VERSION = "preholdout-sensitivity/0.1"
RUNNER_VERSION = "g3c2c-preholdout-live-runner/0.1"
PROVIDER_PROFILE_VERSION = "g3c2c-preholdout-live/0.1"
PROVIDER_ADAPTER_VERSION = "provider-a-live-boundary/0.1"
MODEL_ID = "gpt-5.6-sol"
MAX_ATTEMPTS = 1
MAX_OUTPUT_TOKENS = 1024

_CONFIRMATIONS = {
    "INTERNAL": "I_UNDERSTAND_NINE_INTERNAL_PREHOLDOUT_CALLS_ONLY",
    "CONFIDENTIAL": "I_UNDERSTAND_NINE_CONFIDENTIAL_PREHOLDOUT_CALLS_ONLY",
}


class PreHoldoutRunnerError(RuntimeError):
    """Fail-closed pre-Holdout execution error."""


class PreHoldoutBatchStopped(PreHoldoutRunnerError):
    """Raised after a RED safety/governance condition with a safe partial receipt."""

    def __init__(self, message: str, *, receipt: dict[str, Any]) -> None:
        super().__init__(message)
        self.receipt = receipt


class SensitivityCaseBinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    golden_case_id: str = Field(min_length=1)
    partition: PreHoldoutPartition
    sensitivity: PreHoldoutSensitivity
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PreHoldoutSensitivityBinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    binding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    binding_version: Literal["preholdout-sensitivity/0.1"]
    case_count: int = Field(ge=1)
    cases: tuple[SensitivityCaseBinding, ...]
    dataset_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    holdout_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    partition_counts: dict[str, int]
    sensitivity_counts: dict[str, int]
    source_ledger_ref: str = Field(min_length=1)
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_binding(self) -> "PreHoldoutSensitivityBinding":
        ids = [item.golden_case_id for item in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate golden_case_id in sensitivity binding")
        if self.case_count != len(self.cases):
            raise ValueError("sensitivity binding case_count mismatch")
        observed_partitions = {
            "development": sum(item.partition == "development" for item in self.cases),
            "validation": sum(item.partition == "validation" for item in self.cases),
            "holdout": 0,
        }
        if self.partition_counts != observed_partitions:
            raise ValueError("sensitivity binding partition_counts mismatch")
        observed_sensitivity = {
            "CONFIDENTIAL": sum(item.sensitivity == "CONFIDENTIAL" for item in self.cases),
            "INTERNAL": sum(item.sensitivity == "INTERNAL" for item in self.cases),
        }
        if self.sensitivity_counts != observed_sensitivity:
            raise ValueError("sensitivity binding sensitivity_counts mismatch")
        body = self.model_dump(mode="json", exclude={"binding_sha256"})
        if sha256_json(body) != self.binding_sha256:
            raise ValueError("sensitivity binding digest mismatch")
        return self


class EvidenceSnippet(BaseModel):
    """Candidate-visible evidence only; source URLs and oracle fields stay outside provider payload."""

    model_config = ConfigDict(frozen=True)

    ref: str = Field(min_length=1)
    text: str = Field(min_length=1)
    sensitivity: PreHoldoutSensitivity
    epistemic_class: EpistemicClass = EpistemicClass.DOCUMENTED_FACT


class PrivatePreHoldoutCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case: GoldenCase
    sensitivity: PreHoldoutSensitivity
    evidence: tuple[EvidenceSnippet, ...] = ()


class PrivatePreHoldoutBundle(BaseModel):
    """Private local-only bundle. It must never be committed to the public repository."""

    model_config = ConfigDict(frozen=True)

    dataset_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    sensitivity_scope: PreHoldoutSensitivity
    cases: tuple[PrivatePreHoldoutCase, ...] = Field(min_length=1)


class BatchCaseFailure(BaseModel):
    model_config = ConfigDict(frozen=True)

    golden_case_id: str
    kind: Literal["PROVIDER_TRANSPORT", "RED_SAFETY_OR_GOVERNANCE"]
    detail_code: str
    transport_attempted: bool


class BatchPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    dataset_id: str
    dataset_version: str
    sensitivity_scope: PreHoldoutSensitivity
    case_ids: tuple[str, ...]
    case_count: int
    binding_sha256: str
    expected_main_sha: str
    provider: Literal["openai"] = "openai"
    model: Literal["gpt-5.6-sol"] = "gpt-5.6-sol"
    reasoning: Literal["high"] = "high"
    max_attempts: Literal[1] = 1
    max_output_tokens: Literal[1024] = 1024
    holdout: Literal[False] = False
    tools_enabled: Literal[False] = False
    full_dataset: Literal[False] = False
    g3_quality_pass_claimed: Literal[False] = False


def load_sensitivity_binding(path: str | Path) -> PreHoldoutSensitivityBinding:
    return PreHoldoutSensitivityBinding.model_validate(
        json.loads(Path(path).read_text(encoding="utf-8"))
    )


def load_dataset_manifest(path: str | Path) -> GoldenDatasetManifest:
    return GoldenDatasetManifest.model_validate(
        json.loads(Path(path).read_text(encoding="utf-8"))
    )


def load_private_bundle(path: str | Path) -> PrivatePreHoldoutBundle:
    return PrivatePreHoldoutBundle.model_validate(
        json.loads(Path(path).read_text(encoding="utf-8"))
    )


def canonical_case_sha256(case: GoldenCase) -> str:
    """Digest over the exact GoldenCase contract used by the v0.2 ledger content_sha256."""

    return sha256_json(case.model_dump(mode="json"))


def evidence_alias(ref: str) -> str:
    return f"e{sha256_json({'ref': ref})[:12]}"


def _sensitivity_rank(value: str) -> int:
    return {"INTERNAL": 1, "CONFIDENTIAL": 2}[value]


def verify_preholdout_binding(
    *,
    binding: PreHoldoutSensitivityBinding,
    manifest: GoldenDatasetManifest,
) -> dict[str, Any]:
    if binding.dataset_id != manifest.dataset_id:
        raise PreHoldoutRunnerError("binding/manifest dataset_id mismatch")
    if binding.dataset_version != manifest.dataset_version:
        raise PreHoldoutRunnerError("binding/manifest dataset_version mismatch")

    manifest_index = {item.golden_case_id: item for item in manifest.cases}
    if len(manifest_index) != len(manifest.cases):
        raise PreHoldoutRunnerError("duplicate golden_case_id in dataset manifest")

    expected = {
        case_id
        for case_id, item in manifest_index.items()
        if item.partition in {"development", "validation"}
    }
    observed = {item.golden_case_id for item in binding.cases}
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise PreHoldoutRunnerError(
            f"pre-Holdout binding coverage mismatch; missing={missing}, extra={extra}"
        )

    for item in binding.cases:
        manifest_item = manifest_index[item.golden_case_id]
        if manifest_item.partition != item.partition:
            raise PreHoldoutRunnerError(
                f"binding partition mismatch for {item.golden_case_id}"
            )
        if manifest_item.content_sha256 != item.content_sha256:
            raise PreHoldoutRunnerError(
                f"binding content digest mismatch for {item.golden_case_id}"
            )

    return {
        "dataset_id": binding.dataset_id,
        "dataset_version": binding.dataset_version,
        "binding_sha256": binding.binding_sha256,
        "case_count": len(binding.cases),
        "partition_counts": binding.partition_counts,
        "sensitivity_counts": binding.sensitivity_counts,
        "holdout_executed": False,
    }


def verify_private_bundle(
    *,
    bundle: PrivatePreHoldoutBundle,
    binding: PreHoldoutSensitivityBinding,
    manifest: GoldenDatasetManifest,
) -> dict[str, Any]:
    verify_preholdout_binding(binding=binding, manifest=manifest)
    if bundle.dataset_id != binding.dataset_id:
        raise PreHoldoutRunnerError("private bundle dataset_id mismatch")
    if bundle.dataset_version != binding.dataset_version:
        raise PreHoldoutRunnerError("private bundle dataset_version mismatch")

    binding_index = {item.golden_case_id: item for item in binding.cases}
    expected_ids = {
        item.golden_case_id
        for item in binding.cases
        if item.sensitivity == bundle.sensitivity_scope
    }
    bundle_ids = [item.case.golden_case_id for item in bundle.cases]
    if len(bundle_ids) != len(set(bundle_ids)):
        raise PreHoldoutRunnerError("duplicate golden_case_id in private bundle")
    observed_ids = set(bundle_ids)
    if observed_ids != expected_ids:
        missing = sorted(expected_ids - observed_ids)
        extra = sorted(observed_ids - expected_ids)
        raise PreHoldoutRunnerError(
            f"private bundle sensitivity-scope coverage mismatch; missing={missing}, extra={extra}"
        )

    for payload in bundle.cases:
        case = payload.case
        if case.partition == "holdout":
            raise PreHoldoutRunnerError("Holdout case present in private bundle")
        bound = binding_index[case.golden_case_id]
        if payload.sensitivity != bundle.sensitivity_scope:
            raise PreHoldoutRunnerError(
                f"bundle sensitivity drift for {case.golden_case_id}"
            )
        if bound.sensitivity != payload.sensitivity:
            raise PreHoldoutRunnerError(
                f"ledger sensitivity mismatch for {case.golden_case_id}"
            )
        if bound.partition != case.partition:
            raise PreHoldoutRunnerError(
                f"bundle partition mismatch for {case.golden_case_id}"
            )
        if canonical_case_sha256(case) != bound.content_sha256:
            raise PreHoldoutRunnerError(
                f"GoldenCase payload digest mismatch for {case.golden_case_id}"
            )

        refs = [item.ref for item in payload.evidence]
        if len(refs) != len(set(refs)):
            raise PreHoldoutRunnerError(
                f"duplicate evidence ref for {case.golden_case_id}"
            )
        if set(refs) != set(case.allowed_evidence_refs):
            raise PreHoldoutRunnerError(
                f"candidate evidence coverage mismatch for {case.golden_case_id}"
            )
        if set(refs).intersection(case.forbidden_future_refs):
            raise PreHoldoutRunnerError(
                f"forbidden future evidence present for {case.golden_case_id}"
            )
        if not set(case.required_provenance).issubset(set(refs)):
            raise PreHoldoutRunnerError(
                f"required provenance lacks candidate evidence for {case.golden_case_id}"
            )
        for evidence in payload.evidence:
            if _sensitivity_rank(evidence.sensitivity) > _sensitivity_rank(payload.sensitivity):
                raise PreHoldoutRunnerError(
                    f"evidence sensitivity exceeds case sensitivity for {case.golden_case_id}"
                )

    return {
        "dataset_id": bundle.dataset_id,
        "dataset_version": bundle.dataset_version,
        "sensitivity_scope": bundle.sensitivity_scope,
        "case_count": len(bundle.cases),
        "case_ids": tuple(sorted(bundle_ids)),
        "binding_sha256": binding.binding_sha256,
        "private_payload_committed": False,
        "holdout_executed": False,
    }


def build_candidate_context(
    payload: PrivatePreHoldoutCase,
    *,
    recorded_at: datetime,
) -> ContextBundle:
    memory: list[dict[str, Any]] = []
    for item in payload.evidence:
        memory.append(
            {
                "memory_id": evidence_alias(item.ref),
                "project_scope": payload.case.project_scope,
                "claim": f"[evidence_alias={evidence_alias(item.ref)}] {item.text}",
                "epistemic_class": item.epistemic_class.value,
                "sensitivity": item.sensitivity,
            }
        )
    return ContextBundle(
        project_scope=payload.case.project_scope,
        valid_at=payload.case.cutoff_time,
        recorded_at=recorded_at,
        memory=tuple(memory),
        evidence_refs=tuple(item.ref for item in payload.evidence),
        session_items=(),
    )


def _current_head_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _confirmation_for(scope: PreHoldoutSensitivity) -> str:
    return _CONFIRMATIONS[scope]


def preflight_batch_plan(
    *,
    bundle: PrivatePreHoldoutBundle,
    binding: PreHoldoutSensitivityBinding,
    manifest: GoldenDatasetManifest,
    expected_main_sha: str,
    r2_authority_ref: str,
    one_batch_confirmation: str,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    verified = verify_private_bundle(
        bundle=bundle,
        binding=binding,
        manifest=manifest,
    )
    if not r2_authority_ref.strip():
        raise PreHoldoutRunnerError("R2 authority reference is required")
    if one_batch_confirmation != _confirmation_for(bundle.sensitivity_scope):
        raise PreHoldoutRunnerError("batch confirmation does not match sensitivity scope")
    observed_head = current_head_sha if current_head_sha is not None else _current_head_sha()
    if observed_head != expected_main_sha:
        raise PreHoldoutRunnerError(
            f"exact-main drift; expected={expected_main_sha}, observed={observed_head}"
        )

    plan = BatchPlan(
        dataset_id=bundle.dataset_id,
        dataset_version=bundle.dataset_version,
        sensitivity_scope=bundle.sensitivity_scope,
        case_ids=verified["case_ids"],
        case_count=verified["case_count"],
        binding_sha256=binding.binding_sha256,
        expected_main_sha=expected_main_sha,
    )
    body = {
        "runner_version": RUNNER_VERSION,
        "r2_authority_ref": r2_authority_ref.strip(),
        "one_batch_confirmation": one_batch_confirmation,
        "plan": plan.model_dump(mode="json"),
    }
    return {
        **body,
        "execution_intent_sha256": sha256_json(body),
        "credential_read": False,
        "outbound_executed": False,
    }


def _safe_batch_receipt(
    *,
    bundle: PrivatePreHoldoutBundle,
    binding: PreHoldoutSensitivityBinding,
    expected_main_sha: str,
    r2_authority_ref: str,
    execution_intent_sha256: str,
    traces: tuple[dict[str, Any], ...],
    observations: tuple[Any, ...],
    failures: tuple[BatchCaseFailure, ...],
    quality_failures_by_case: dict[str, tuple[str, ...]],
    safety_failures_by_case: dict[str, tuple[str, ...]],
    stopped: bool,
    stop_reason: str | None,
) -> dict[str, Any]:
    trace_receipt: dict[str, Any] | None = None
    if traces:
        expected_identity = traces[0]["candidate"]
        identity = ProviderALiveConfig(
            profile_version=PROVIDER_PROFILE_VERSION,
            adapter_version=PROVIDER_ADAPTER_VERSION,
            max_attempts=MAX_ATTEMPTS,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        ).identity()
        if expected_identity != identity.model_dump(mode="json"):
            raise PreHoldoutRunnerError("provider identity drift in safe receipt")
        trace_receipt = live_provider_trace_receipt(
            traces=traces,
            expected_identity=identity,
            expected_r2_authority_ref=r2_authority_ref,
        )

    aggregation = aggregate_quality(observations) if observations else None
    body = {
        "runner_version": RUNNER_VERSION,
        "dataset_id": bundle.dataset_id,
        "dataset_version": bundle.dataset_version,
        "binding_sha256": binding.binding_sha256,
        "main_sha": expected_main_sha,
        "r2_authority_ref": r2_authority_ref,
        "execution_intent_sha256": execution_intent_sha256,
        "sensitivity_scope": bundle.sensitivity_scope,
        "planned_case_count": len(bundle.cases),
        "completed_trace_count": len(traces),
        "case_ids": [item.case.golden_case_id for item in bundle.cases],
        "external_provider_calls": sum(int(trace["external_provider_calls"]) for trace in traces),
        "transport_attempt_count": (
            sum(int(trace["transport_attempt_count"]) for trace in traces)
            + sum(1 for item in failures if item.transport_attempted)
        ),
        "transport_failure_count": sum(item.kind == "PROVIDER_TRANSPORT" for item in failures),
        "quality_failures_by_case": {
            key: list(value) for key, value in sorted(quality_failures_by_case.items())
        },
        "safety_failures_by_case": {
            key: list(value) for key, value in sorted(safety_failures_by_case.items())
        },
        "failures": [item.model_dump(mode="json") for item in failures],
        "quality_aggregation": (
            aggregation.model_dump(mode="json") if aggregation is not None else None
        ),
        "trace_receipt_sha256": (
            trace_receipt["receipt_sha256"] if trace_receipt is not None else None
        ),
        "stopped": stopped,
        "stop_reason": stop_reason,
        "holdout": False,
        "full_dataset": False,
        "tools_enabled": False,
        "g3_quality_pass_claimed": False,
    }
    return {**body, "receipt_sha256": sha256_json(body)}


def execute_preholdout_batch(
    *,
    bundle: PrivatePreHoldoutBundle,
    binding: PreHoldoutSensitivityBinding,
    manifest: GoldenDatasetManifest,
    adapter: ProviderALiveAdapter,
    expected_main_sha: str,
    r2_authority_ref: str,
    execution_intent_sha256: str,
    recorded_at: datetime | None = None,
) -> dict[str, Any]:
    verify_private_bundle(bundle=bundle, binding=binding, manifest=manifest)
    if adapter.config.max_attempts != 1:
        raise PreHoldoutRunnerError("pre-Holdout batch requires max_attempts=1")
    if adapter.config.model_id != MODEL_ID:
        raise PreHoldoutRunnerError("pre-Holdout model identity drift")
    if adapter.config.profile_version != PROVIDER_PROFILE_VERSION:
        raise PreHoldoutRunnerError("pre-Holdout provider profile drift")
    if adapter.config.adapter_version != PROVIDER_ADAPTER_VERSION:
        raise PreHoldoutRunnerError("pre-Holdout adapter version drift")
    if adapter.data_policy.max_sensitivity != bundle.sensitivity_scope:
        raise PreHoldoutRunnerError(
            "outbound data policy must exactly match bundle sensitivity scope"
        )
    if not r2_authority_ref.strip():
        raise PreHoldoutRunnerError("R2 authority reference is required")

    at = recorded_at or datetime.now(timezone.utc)
    traces: list[dict[str, Any]] = []
    observations: list[Any] = []
    failures: list[BatchCaseFailure] = []
    quality_failures_by_case: dict[str, tuple[str, ...]] = {}
    safety_failures_by_case: dict[str, tuple[str, ...]] = {}

    for payload in sorted(bundle.cases, key=lambda item: item.case.golden_case_id):
        context = build_candidate_context(payload, recorded_at=at)
        try:
            trace = adapter.execute(
                case=payload.case,
                context=context,
                r2_authority_ref=r2_authority_ref,
            )
        except ProviderLiveBoundaryError as exc:
            if isinstance(exc.__cause__, ProviderLiveTransportError):
                failures.append(
                    BatchCaseFailure(
                        golden_case_id=payload.case.golden_case_id,
                        kind="PROVIDER_TRANSPORT",
                        detail_code="PROVIDER_TRANSPORT_NO_RETRY",
                        transport_attempted=True,
                    )
                )
                continue

            failures.append(
                BatchCaseFailure(
                    golden_case_id=payload.case.golden_case_id,
                    kind="RED_SAFETY_OR_GOVERNANCE",
                    detail_code=type(exc).__name__,
                    transport_attempted=False,
                )
            )
            partial = _safe_batch_receipt(
                bundle=bundle,
                binding=binding,
                expected_main_sha=expected_main_sha,
                r2_authority_ref=r2_authority_ref,
                execution_intent_sha256=execution_intent_sha256,
                traces=tuple(traces),
                observations=tuple(observations),
                failures=tuple(failures),
                quality_failures_by_case=quality_failures_by_case,
                safety_failures_by_case=safety_failures_by_case,
                stopped=True,
                stop_reason="RED_PROVIDER_BOUNDARY",
            )
            raise PreHoldoutBatchStopped(
                "RED provider boundary failure; batch stopped fail-closed",
                receipt=partial,
            ) from exc

        traces.append(trace)
        result = evaluate_golden_case(payload.case, trace)
        quality_failures_by_case[payload.case.golden_case_id] = result.quality_failures
        safety_failures_by_case[payload.case.golden_case_id] = result.safety_failures
        observation = quality_observation_from_trace(case=payload.case, trace=trace)
        observations.append(observation)

        if result.safety_failures:
            failures.append(
                BatchCaseFailure(
                    golden_case_id=payload.case.golden_case_id,
                    kind="RED_SAFETY_OR_GOVERNANCE",
                    detail_code="DETERMINISTIC_SAFETY_FAILURE",
                    transport_attempted=True,
                )
            )
            partial = _safe_batch_receipt(
                bundle=bundle,
                binding=binding,
                expected_main_sha=expected_main_sha,
                r2_authority_ref=r2_authority_ref,
                execution_intent_sha256=execution_intent_sha256,
                traces=tuple(traces),
                observations=tuple(observations),
                failures=tuple(failures),
                quality_failures_by_case=quality_failures_by_case,
                safety_failures_by_case=safety_failures_by_case,
                stopped=True,
                stop_reason="RED_DETERMINISTIC_SAFETY_FAILURE",
            )
            raise PreHoldoutBatchStopped(
                "RED deterministic safety failure; batch stopped fail-closed",
                receipt=partial,
            )

    return _safe_batch_receipt(
        bundle=bundle,
        binding=binding,
        expected_main_sha=expected_main_sha,
        r2_authority_ref=r2_authority_ref,
        execution_intent_sha256=execution_intent_sha256,
        traces=tuple(traces),
        observations=tuple(observations),
        failures=tuple(failures),
        quality_failures_by_case=quality_failures_by_case,
        safety_failures_by_case=safety_failures_by_case,
        stopped=False,
        stop_reason=None,
    )


def _fixed_live_adapter(scope: PreHoldoutSensitivity) -> ProviderALiveAdapter:
    config = ProviderALiveConfig(
        profile_version=PROVIDER_PROFILE_VERSION,
        adapter_version=PROVIDER_ADAPTER_VERSION,
        max_attempts=MAX_ATTEMPTS,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    policy = OutboundDataPolicy(max_sensitivity=scope)
    return ProviderALiveAdapter(
        config=config,
        data_policy=policy,
        http_client=UrllibProviderAHTTPClient(),
        environment=os.environ,
    )


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _cli() -> int:
    parser = argparse.ArgumentParser(description="SOAiaCore G3C2C pre-Holdout LIVE runner")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate binding/private bundle; no outbound")
    validate.add_argument("--binding", required=True)
    validate.add_argument("--manifest", required=True)
    validate.add_argument("--bundle", required=True)

    preflight = sub.add_parser("preflight", help="create exact batch intent; no credential read")
    preflight.add_argument("--binding", required=True)
    preflight.add_argument("--manifest", required=True)
    preflight.add_argument("--bundle", required=True)
    preflight.add_argument("--expected-main-sha", required=True)
    preflight.add_argument("--r2-authority-ref", required=True)
    preflight.add_argument("--one-batch-confirmation", required=True)
    preflight.add_argument("--intent-out", required=True)

    execute = sub.add_parser("execute", help="execute one R2-authorized pre-Holdout batch")
    execute.add_argument("--binding", required=True)
    execute.add_argument("--manifest", required=True)
    execute.add_argument("--bundle", required=True)
    execute.add_argument("--expected-main-sha", required=True)
    execute.add_argument("--r2-authority-ref", required=True)
    execute.add_argument("--one-batch-confirmation", required=True)
    execute.add_argument("--intent-file", required=True)
    execute.add_argument("--intent-lock", required=True)
    execute.add_argument("--receipt-out", required=True)

    args = parser.parse_args()
    binding = load_sensitivity_binding(args.binding)
    manifest = load_dataset_manifest(args.manifest)
    bundle = load_private_bundle(args.bundle)

    if args.command == "validate":
        result = verify_private_bundle(
            bundle=bundle,
            binding=binding,
            manifest=manifest,
        )
        print(json.dumps(result, sort_keys=True))
        return 0

    plan = preflight_batch_plan(
        bundle=bundle,
        binding=binding,
        manifest=manifest,
        expected_main_sha=args.expected_main_sha,
        r2_authority_ref=args.r2_authority_ref,
        one_batch_confirmation=args.one_batch_confirmation,
    )

    if args.command == "preflight":
        _write_json(args.intent_out, plan)
        print(json.dumps(plan, sort_keys=True))
        return 0

    intent_path = Path(args.intent_file)
    lock_path = Path(args.intent_lock)
    if lock_path.exists():
        raise PreHoldoutRunnerError("local replay lock already exists")
    stored_intent = json.loads(intent_path.read_text(encoding="utf-8"))
    if stored_intent != plan:
        raise PreHoldoutRunnerError("execution intent file mismatch")
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise PreHoldoutRunnerError("OPENAI_API_KEY is missing from runtime environment")

    lock_path.write_text(
        plan["execution_intent_sha256"] + "\n",
        encoding="utf-8",
    )
    try:
        receipt = execute_preholdout_batch(
            bundle=bundle,
            binding=binding,
            manifest=manifest,
            adapter=_fixed_live_adapter(bundle.sensitivity_scope),
            expected_main_sha=args.expected_main_sha,
            r2_authority_ref=args.r2_authority_ref,
            execution_intent_sha256=plan["execution_intent_sha256"],
        )
    except PreHoldoutBatchStopped as exc:
        _write_json(args.receipt_out, exc.receipt)
        raise
    _write_json(args.receipt_out, receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
