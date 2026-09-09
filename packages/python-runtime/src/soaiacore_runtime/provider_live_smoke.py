from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cognitive_loop import ContextBundle, EpistemicClass
from .golden_eval import GoldenCase
from .hashing import sha256_json
from .provider_live import (
    OutboundDataPolicy,
    ProviderAHTTPClient,
    ProviderALiveAdapter,
    ProviderALiveConfig,
    ProviderLiveBoundaryError,
    UrllibProviderAHTTPClient,
    live_provider_trace_receipt,
    prepare_g3c2b0_live_request,
    validate_live_trace,
)


SMOKE_CASE_ID = "G3C2B1-SYNTHETIC-LIVE-SMOKE-001"
SMOKE_PARTITION = "development"
SMOKE_PROJECT_SCOPE = "SOAiaCore"
SMOKE_PROFILE_VERSION = "g3c2b1-synthetic-live-smoke/0.1"
SMOKE_ADAPTER_VERSION = "provider-a-live-boundary/0.1"
SMOKE_BOUNDARY_VERSION = "g3c2b1-single-shot-harness/0.1"
SMOKE_OUTBOUND_PERMIT_ENV = "SOAIACORE_G3C2B1_ALLOW_OUTBOUND"
SMOKE_MAX_OUTPUT_TOKENS = 512
SMOKE_MAX_ATTEMPTS = 1
SMOKE_TIMEOUT_SECONDS = 30.0
SMOKE_REQUIRED_CONFIRMATION = "I_UNDERSTAND_ONE_PUBLIC_SYNTHETIC_CALL_ONLY"
_MAIN_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class SingleShotSmokeError(RuntimeError):
    """Fail-closed error for the governed G3C2B1 synthetic smoke harness."""


def _synthetic_case() -> GoldenCase:
    """Return the one fixed synthetic development case allowed by G3C2B1."""

    now = datetime(2026, 9, 8, 22, 0, tzinfo=timezone.utc)
    return GoldenCase(
        golden_case_id=SMOKE_CASE_ID,
        project_scope=SMOKE_PROJECT_SCOPE,
        question=(
            "Synthetic connectivity smoke only. The supplied public synthetic context states "
            "ALPHA_SMOKE=READY. Return a concise confirmation using epistemic class "
            "CONFIRMED_CONTEXT and disposition CLAIM_PROPOSAL. Do not request tools or any "
            "material effect. Set memory_admission_decision to REJECT and decision_state to READY."
        ),
        cutoff_time=now,
        allowed_evidence_refs=("synthetic:g3c2b1:ready",),
        forbidden_future_refs=(),
        expected_epistemic_class=EpistemicClass.CONFIRMED_CONTEXT,
        expected_claims=("Synthetic ALPHA_SMOKE state is READY.",),
        expected_decision_state="READY",
        contradictions_expected=(),
        required_provenance=("synthetic:g3c2b1:ready",),
        forbidden_tool_classes=("ANY_TOOL",),
        notes="Synthetic non-sensitive connectivity smoke; never use as a cognition-quality benchmark.",
        partition=SMOKE_PARTITION,
    )


def _synthetic_context() -> ContextBundle:
    now = datetime(2026, 9, 8, 22, 0, tzinfo=timezone.utc)
    return ContextBundle(
        project_scope=SMOKE_PROJECT_SCOPE,
        valid_at=now,
        recorded_at=now,
        memory=(
            {
                "memory_id": "SYNTHETIC-MEM-G3C2B1-001",
                "project_scope": SMOKE_PROJECT_SCOPE,
                "claim": "Synthetic ALPHA_SMOKE state is READY.",
                "epistemic_class": "CONFIRMED_CONTEXT",
                "sensitivity": "PUBLIC",
            },
        ),
        evidence_refs=("synthetic:g3c2b1:ready",),
        session_items=(),
    )


def _config() -> ProviderALiveConfig:
    return ProviderALiveConfig(
        profile_version=SMOKE_PROFILE_VERSION,
        adapter_version=SMOKE_ADAPTER_VERSION,
        max_attempts=SMOKE_MAX_ATTEMPTS,
        timeout_seconds=SMOKE_TIMEOUT_SECONDS,
        max_output_tokens=SMOKE_MAX_OUTPUT_TOKENS,
    )


def _data_policy() -> OutboundDataPolicy:
    return OutboundDataPolicy(
        max_sensitivity="PUBLIC",
        memory_field_allowlist=(
            "memory_id",
            "project_scope",
            "claim",
            "epistemic_class",
            "sensitivity",
        ),
        session_payload_allowlist=(),
    )


def _smoke_spec() -> dict[str, Any]:
    return {
        "harness_version": SMOKE_BOUNDARY_VERSION,
        "golden_case_id": SMOKE_CASE_ID,
        "partition": SMOKE_PARTITION,
        "project_scope": SMOKE_PROJECT_SCOPE,
        "synthetic_only": True,
        "sensitivity": "PUBLIC",
        "single_shot": True,
        "max_attempts": SMOKE_MAX_ATTEMPTS,
        "max_output_tokens": SMOKE_MAX_OUTPUT_TOKENS,
        "full_dataset_evaluation": False,
        "holdout_allowed": False,
        "g3_quality_pass_claimed": False,
    }


def _execution_intent(
    *,
    expected_main_sha: str,
    r2_authority_ref: str,
    workflow_run_id: str,
    one_call_confirmation: str,
    payload_sha256: str,
    config: ProviderALiveConfig,
) -> dict[str, Any]:
    main_sha = expected_main_sha.strip().lower()
    authority = r2_authority_ref.strip()
    run_id = workflow_run_id.strip()
    if not _MAIN_SHA_PATTERN.fullmatch(main_sha):
        raise SingleShotSmokeError("expected main SHA is not a 40-character lowercase commit SHA")
    if not authority:
        raise SingleShotSmokeError("execution intent requires a non-empty R2 authority ref")
    if not run_id:
        raise SingleShotSmokeError("execution intent requires a non-empty workflow run identity")
    if one_call_confirmation.strip() != SMOKE_REQUIRED_CONFIRMATION:
        raise SingleShotSmokeError("one-call confirmation literal is invalid")
    body = {
        "r2_authority_ref": authority,
        "expected_main_sha": main_sha,
        "case_id": SMOKE_CASE_ID,
        "provider": config.provider,
        "model": config.model_id,
        "profile_version": config.profile_version,
        "payload_sha256": payload_sha256,
        "workflow_run_id": run_id,
        "one_call_confirmation": SMOKE_REQUIRED_CONFIRMATION,
    }
    return {**body, "intent_sha256": sha256_json(body)}


def _load_execution_intent(path: str) -> dict[str, Any]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SingleShotSmokeError("execution intent file is missing or malformed") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("execution_intent"), dict):
        raise SingleShotSmokeError("execution intent file does not contain an execution_intent object")
    return raw["execution_intent"]


def _claim_execution_intent(intent: dict[str, Any], lock_path: str | None) -> None:
    if not lock_path:
        return
    target = Path(lock_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise SingleShotSmokeError("execution intent replay detected; lock already exists") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"intent_sha256": intent["intent_sha256"]}, sort_keys=True))
            handle.write("\n")
    except Exception:
        target.unlink(missing_ok=True)
        raise


def preflight_single_shot_smoke(
    *,
    expected_main_sha: str | None = None,
    r2_authority_ref: str | None = None,
    workflow_run_id: str | None = None,
    one_call_confirmation: str | None = None,
) -> dict[str, Any]:
    """Prepare the fixed synthetic request without reading credentials or opening a socket."""

    case = _synthetic_case()
    context = _synthetic_context()
    config = _config()
    prepared = prepare_g3c2b0_live_request(
        case=case,
        context=context,
        config=config,
        data_policy=_data_policy(),
    )
    body = {
        **_smoke_spec(),
        "candidate": config.identity().model_dump(mode="json"),
        "payload_sha256": prepared.payload_sha256,
        "client_request_id": prepared.client_request_id,
        "external_provider_calls": 0,
        "credential_read": False,
        "outbound_executed": False,
    }
    intent_values = (expected_main_sha, r2_authority_ref, workflow_run_id, one_call_confirmation)
    if any(value is not None for value in intent_values):
        if not all(value is not None for value in intent_values):
            raise SingleShotSmokeError("execution intent requires expected SHA, authority ref, and workflow run ID")
        body["execution_intent"] = _execution_intent(
            expected_main_sha=expected_main_sha or "",
            r2_authority_ref=r2_authority_ref or "",
            workflow_run_id=workflow_run_id or "",
            one_call_confirmation=one_call_confirmation or "",
            payload_sha256=prepared.payload_sha256,
            config=config,
        )
    return {**body, "preflight_sha256": sha256_json(body)}


def _require_outbound_permit(environment: Mapping[str, str]) -> None:
    if environment.get(SMOKE_OUTBOUND_PERMIT_ENV, "").strip() != "1":
        raise SingleShotSmokeError(
            f"single-shot LIVE execution requires {SMOKE_OUTBOUND_PERMIT_ENV}=1"
        )


def run_single_shot_smoke(
    *,
    r2_authority_ref: str,
    expected_main_sha: str,
    workflow_run_id: str,
    one_call_confirmation: str,
    http_client: ProviderAHTTPClient | None = None,
    environment: Mapping[str, str] | None = None,
    expected_intent: dict[str, Any] | None = None,
    intent_lock_path: str | None = None,
) -> dict[str, Any]:
    """Execute exactly one fixed PUBLIC synthetic Provider A call after explicit R2 gating.

    This function accepts no caller-supplied case, context, partition, model, retry count,
    output budget, or data policy. It therefore cannot be repurposed by configuration to
    evaluate development/validation corpora or Holdout.
    """

    authority = r2_authority_ref.strip()
    if not authority:
        raise SingleShotSmokeError("single-shot LIVE execution requires an exact R2 authority ref")

    env = environment if environment is not None else os.environ
    _require_outbound_permit(env)

    config = _config()
    prepared = prepare_g3c2b0_live_request(
        case=_synthetic_case(),
        context=_synthetic_context(),
        config=config,
        data_policy=_data_policy(),
    )
    intent = _execution_intent(
        expected_main_sha=expected_main_sha,
        r2_authority_ref=authority,
        workflow_run_id=workflow_run_id,
        one_call_confirmation=one_call_confirmation,
        payload_sha256=prepared.payload_sha256,
        config=config,
    )
    if expected_intent is not None and expected_intent != intent:
        raise SingleShotSmokeError("execution intent drift or replay mismatch")
    _claim_execution_intent(intent, intent_lock_path)

    client = http_client if http_client is not None else UrllibProviderAHTTPClient()
    adapter = ProviderALiveAdapter(
        config=config,
        data_policy=_data_policy(),
        http_client=client,
        environment=env,
    )
    trace = adapter.execute(
        case=_synthetic_case(),
        context=_synthetic_context(),
        r2_authority_ref=authority,
    )
    trace_ref = validate_live_trace(trace=trace, expected_identity=config.identity())
    if trace.get("golden_case_id") != SMOKE_CASE_ID:
        raise SingleShotSmokeError("single-shot trace case identity drift")
    if trace.get("partition") != SMOKE_PARTITION:
        raise SingleShotSmokeError("single-shot trace partition drift")
    if trace.get("external_provider_calls") != 1:
        raise SingleShotSmokeError("single-shot harness must record exactly one provider call")
    if trace.get("transport_attempt_count") != 1:
        raise SingleShotSmokeError("single-shot harness forbids transport retries")

    if trace["payload_sha256"] != intent["payload_sha256"]:
        raise SingleShotSmokeError("provider payload digest drift")

    boundary_receipt = live_provider_trace_receipt(
        traces=(trace,),
        expected_identity=config.identity(),
        expected_r2_authority_ref=authority,
    )
    if boundary_receipt.get("case_count") != 1:
        raise SingleShotSmokeError("single-shot receipt case count drift")
    if boundary_receipt.get("partition_counts") != {
        "development": 1,
        "validation": 0,
        "holdout": 0,
    }:
        raise SingleShotSmokeError("single-shot receipt partition count drift")

    body = {
        **_smoke_spec(),
        "candidate": config.identity().model_dump(mode="json"),
        "main_sha": intent["expected_main_sha"],
        "r2_authority_ref": authority,
        "case_id": SMOKE_CASE_ID,
        "provider": config.provider,
        "model": config.model_id,
        "profile_version": config.profile_version,
        "workflow_run_id": intent["workflow_run_id"],
        "execution_intent_sha256": intent["intent_sha256"],
        "external_provider_calls": 1,
        "transport_attempt_count": 1,
        "Holdout": False,
        "full_dataset": False,
        "G3_quality_pass": False,
        "trace_ref": trace_ref,
        "trace_sha256": trace["trace_sha256"],
        "payload_sha256": trace["payload_sha256"],
        "provider_trace_sha256": trace["trace_sha256"],
        "provider_payload_sha256": trace["payload_sha256"],
        "boundary_receipt_sha256": boundary_receipt["receipt_sha256"],
        "provider_request_id": trace.get("provider_request_id", ""),
        "client_request_id": trace.get("client_request_id", ""),
        "provider_response_id": trace.get("provider_response_id", ""),
        "provider_reported_model": trace.get("provider_reported_model", ""),
        "oracle_fields_exposed": False,
        "holdout_executed": False,
        "tools_enabled": False,
    }
    receipt = {**body, "receipt_sha256": sha256_json(body)}
    return {
        "trace": trace,
        "boundary_receipt": boundary_receipt,
        "single_shot_receipt": receipt,
    }


def _write_json(path: str, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Governed G3C2B1 synthetic LIVE smoke harness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "preflight",
        help="prepare and hash the fixed synthetic request without credential or network access",
    )
    preflight = subparsers.choices["preflight"]
    preflight.add_argument("--expected-main-sha")
    preflight.add_argument("--r2-authority-ref")
    preflight.add_argument("--workflow-run-id")
    preflight.add_argument("--one-call-confirmation")
    preflight.add_argument("--intent-out")

    execute = subparsers.add_parser(
        "execute",
        help="execute exactly one fixed PUBLIC synthetic provider call after an R2 permit",
    )
    execute.add_argument("--r2-authority-ref", required=True)
    execute.add_argument("--expected-main-sha", required=True)
    execute.add_argument("--workflow-run-id", required=True)
    execute.add_argument("--one-call-confirmation", required=True)
    execute.add_argument("--intent-file", required=True)
    execute.add_argument("--intent-lock", required=True)
    execute.add_argument("--receipt-out", required=True)

    args = parser.parse_args(argv)
    if args.command == "preflight":
        intent_args = {
            "expected_main_sha": getattr(args, "expected_main_sha", None),
            "r2_authority_ref": getattr(args, "r2_authority_ref", None),
            "workflow_run_id": getattr(args, "workflow_run_id", None),
            "one_call_confirmation": getattr(args, "one_call_confirmation", None),
        }
        result = preflight_single_shot_smoke(**intent_args)
        intent_out = getattr(args, "intent_out", None)
        if intent_out:
            _write_json(intent_out, result)
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "execute":
        intent_file = _load_execution_intent(args.intent_file)
        result = run_single_shot_smoke(
            r2_authority_ref=args.r2_authority_ref,
            expected_main_sha=args.expected_main_sha,
            workflow_run_id=args.workflow_run_id,
            one_call_confirmation=args.one_call_confirmation,
            expected_intent=intent_file,
            intent_lock_path=args.intent_lock,
        )
        _write_json(args.receipt_out, result)
        print(
            json.dumps(
                {
                    "status": "SINGLE_SHOT_COMPLETE",
                    "receipt_sha256": result["single_shot_receipt"]["receipt_sha256"],
                    "external_provider_calls": 1,
                    "holdout_executed": False,
                    "g3_quality_pass_claimed": False,
                },
                sort_keys=True,
            )
        )
        return 0

    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
