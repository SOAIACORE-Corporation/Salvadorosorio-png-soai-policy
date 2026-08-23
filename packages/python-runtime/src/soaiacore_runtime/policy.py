from __future__ import annotations

from typing import Any

from .identifiers import deterministic_id
from .schemas import validate_payload


def data_minimization_decision(
    *, run_id: str, purpose: str, synthetic_only: bool, created_at: str
) -> dict[str, Any]:
    if synthetic_only:
        decision = {
            "decision_id": deterministic_id("dmin", run_id),
            "action": "ALLOW",
            "purpose": purpose,
            "provider_eligibility": False,
            "fields_removed": [],
            "fields_tokenized": [],
            "reason_codes": ["P0_SYNTHETIC_MOCK", "EXTERNAL_PROVIDER_DISABLED"],
            "created_at": created_at,
        }
    else:
        decision = {
            "decision_id": deterministic_id("dmin", run_id),
            "action": "DENY",
            "purpose": purpose,
            "provider_eligibility": False,
            "fields_removed": [],
            "fields_tokenized": [],
            "reason_codes": ["P0_SYNTHETIC_ONLY"],
            "created_at": created_at,
        }
    validate_payload("data-minimization-decision-v0.1.schema.json", decision, stage="PRECHECK")
    return decision


def review_policy_decision(
    *,
    run_id: str,
    analysis_profile_id: str,
    profile_mode: str,
    restricted_workflow: bool,
    identity_uncertainty: bool,
    authorization_decision: str,
    created_at: str,
) -> dict[str, Any]:
    reasons: list[str] = []
    if restricted_workflow:
        mode = "REQUIRED"
        reasons.append("RESTRICTED_WORKFLOW")
    elif identity_uncertainty:
        mode = "REQUIRED"
        reasons.append("IDENTITY_UNCERTAINTY")
    elif authorization_decision == "CONDITIONAL":
        mode = "REQUIRED"
        reasons.append("AUTHORIZATION_CONDITIONAL")
    else:
        mode = profile_mode
        reasons.append(f"ANALYSIS_PROFILE_{profile_mode}")

    decision = {
        "review_policy_id": deterministic_id("rpol", run_id),
        "mode": mode,
        "analysis_profile_id": analysis_profile_id,
        "reason_codes": reasons,
        "identity_uncertainty": identity_uncertainty,
        "sensitivity_level": "SYNTHETIC",
        "downstream_consequence": "P0_PILOT_ONLY",
        "created_at": created_at,
    }
    validate_payload("review-policy-v0.1.schema.json", decision, stage="REVIEW_POLICY")
    return decision

