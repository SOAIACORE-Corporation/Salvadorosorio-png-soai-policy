#!/usr/bin/env python3
"""MOCATRIZ continuity test after conversational interruption."""

from __future__ import annotations
from typing import Any

DIMENSIONS = (
    "objective",
    "scope",
    "rules",
    "state",
    "evidence",
    "strategy",
    "resumption",
    "closure",
    "uncertainty",
    "narrative",
)

NULLIFYING_FAILURES = {
    "FALSE_FUNCTIONAL_CLOSURE",
    "MATERIAL_ACTION_DUPLICATION",
    "CRITICAL_RULE_LOSS",
    "UNVERIFIED_SUCCESS_ATTRIBUTION",
    "CHANNEL_TIMEOUT_AS_EXECUTION_FAILURE",
    "EXECUTION_SUCCESS_AS_FUNCTIONAL_SUCCESS",
    "FABRICATED_EVIDENCE",
}


def score_continuity(
    *,
    dimension_scores: dict[str, int],
    nullifying_failures: list[str] | None = None,
) -> dict[str, Any]:
    missing = sorted(set(DIMENSIONS) - set(dimension_scores))
    extra = sorted(set(dimension_scores) - set(DIMENSIONS))
    if missing or extra:
        raise ValueError(f"dimension mismatch missing={missing} extra={extra}")

    for name, score in dimension_scores.items():
        if not isinstance(score, int) or not 0 <= score <= 3:
            raise ValueError(f"{name} score must be integer 0..3")

    failures = sorted(set(nullifying_failures or []))
    unsupported = sorted(set(failures) - NULLIFYING_FAILURES)
    if unsupported:
        raise ValueError("unsupported nullifying failure: " + ", ".join(unsupported))

    total = sum(dimension_scores.values())

    if failures:
        band = "FAIL_NULLIFIED"
        passed = False
    elif total >= 27:
        band = "FUNCTIONAL_CONTINUITY_DEMONSTRATED"
        passed = True
    elif total >= 23:
        band = "ACCEPTABLE_WITH_IMPROVEMENTS"
        passed = True
    elif total >= 18:
        band = "FRAGILE_CONTINUITY"
        passed = False
    else:
        band = "CONTEXT_RECOVERY_FAILURE"
        passed = False

    critical_factors = {
        "objective_preserved": dimension_scores["objective"] > 0,
        "state_recovered": dimension_scores["state"] > 0,
        "rules_preserved": dimension_scores["rules"] > 0,
        "correct_resumption": dimension_scores["resumption"] > 0,
        "closure_evidence_preserved": dimension_scores["closure"] > 0,
    }
    multiplicative_effective = all(critical_factors.values()) and not failures

    return {
        "continuity_test_version": "1.0",
        "score": total,
        "max_score": 30,
        "band": band,
        "passed": passed,
        "nullifying_failures": failures,
        "critical_factors": critical_factors,
        "effective_continuity": multiplicative_effective,
    }


def verify_resume_snapshot(
    baseline: dict[str, Any],
    resumed: dict[str, Any],
) -> dict[str, Any]:
    """Exact-ID continuity verification for durable checkpoints.

    Semantic equivalence is intentionally not guessed here. The checkpoint
    carries canonical IDs for objective, scope, rule set, pending set and
    closure contract; recovery must reproduce them explicitly.
    """
    keys = (
        "objective_id",
        "scope_id",
        "rule_set_id",
        "state_version",
        "closure_contract_id",
    )

    mismatches = {
        key: {"expected": baseline.get(key), "actual": resumed.get(key)}
        for key in keys
        if baseline.get(key) != resumed.get(key)
    }

    baseline_pending = set(baseline.get("pending_ids", []))
    resumed_pending = set(resumed.get("pending_ids", []))
    lost_pending = sorted(baseline_pending - resumed_pending)
    invented_pending = sorted(resumed_pending - baseline_pending)

    baseline_evidence = set(baseline.get("evidence_refs", []))
    resumed_evidence = set(resumed.get("evidence_refs", []))
    lost_evidence = sorted(baseline_evidence - resumed_evidence)

    return {
        "checkpoint_match": not mismatches and not lost_pending and not lost_evidence,
        "mismatches": mismatches,
        "lost_pending_ids": lost_pending,
        "invented_pending_ids": invented_pending,
        "lost_evidence_refs": lost_evidence,
        "execution_continuity": resumed.get("external_execution_status") == "SUCCESS",
        "observation_continuity": resumed.get("observation_channel_status") == "RECOVERED",
        "memory_continuity": not mismatches and not lost_pending,
        "resumption_continuity": resumed.get("resume_from_id") == baseline.get("resume_from_id"),
    }


def closure_claim(
    *,
    build_verified: bool,
    security_verified: bool,
    deployment_verified: bool,
    functional_verified: bool,
) -> dict[str, Any]:
    layers = {
        "build": bool(build_verified),
        "security": bool(security_verified),
        "deployment": bool(deployment_verified),
        "functional": bool(functional_verified),
    }
    if all(layers.values()):
        status = "COMPLETED"
    elif layers["build"] and layers["security"]:
        status = "COMPLETED_WITH_EXCEPTIONS"
    else:
        status = "PENDING"
    return {
        "status": status,
        "layers": layers,
        "functional_closure_allowed": bool(functional_verified),
    }
