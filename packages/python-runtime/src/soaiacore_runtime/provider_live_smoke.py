from __future__ import annotations

import argparse
import json
import os
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


def preflight_single_shot_smoke() -> dict[str, Any]:
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
    return {**body, "preflight_sha256": sha256_json(body)}


def _require_outbound_permit(environment: Mapping[str, str]) -> None:
    if environment.get(SMOKE_OUTBOUND_PERMIT_ENV, "").strip() != "1":
        raise SingleShotSmokeError(
            f"single-shot LIVE execution requires {SMOKE_OUTBOUND_PERMIT_ENV}=1"
        )


def run_single_shot_smoke(
    *,
    r2_authority_ref: str,
    http_client: ProviderAHTTPClient | None = None,
    environment: Mapping[str, str] | None = None,
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
        "r2_authority_ref": authority,
        "external_provider_calls": 1,
        "transport_attempt_count": 1,
        "trace_ref": trace_ref,
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

    execute = subparsers.add_parser(
        "execute",
        help="execute exactly one fixed PUBLIC synthetic provider call after an R2 permit",
    )
    execute.add_argument("--r2-authority-ref", required=True)
    execute.add_argument("--receipt-out", required=True)

    args = parser.parse_args(argv)
    if args.command == "preflight":
        print(json.dumps(preflight_single_shot_smoke(), sort_keys=True))
        return 0

    if args.command == "execute":
        result = run_single_shot_smoke(r2_authority_ref=args.r2_authority_ref)
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
