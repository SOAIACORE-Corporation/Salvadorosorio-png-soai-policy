"""Deterministic regulatory source freshness assessment.

Freshness is derived from verification time and an explicit policy window.
HTTP reachability or page existence never makes a source current by itself.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _parse_utc(value: str) -> datetime:
    if not value or not isinstance(value, str):
        raise ValueError("verified_at is required")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("verified_at must include timezone")
    return parsed.astimezone(timezone.utc)


def assess_freshness(
    *,
    verified_at: str | None,
    now: str,
    due_after_hours: float,
    stale_after_hours: float,
) -> dict[str, Any]:
    if due_after_hours <= 0 or stale_after_hours <= 0:
        raise ValueError("freshness windows must be positive")
    if stale_after_hours < due_after_hours:
        raise ValueError("stale_after_hours must be >= due_after_hours")

    try:
        verified = _parse_utc(verified_at or "")
        current = _parse_utc(now)
    except (ValueError, TypeError):
        return {
            "state": "UNKNOWN",
            "canonical_freshness": "unknown",
            "age_hours": None,
            "analysis_allowed": True,
            "material_execution_allowed": False,
            "reason": "Verification timestamp is missing or invalid.",
        }

    age_hours = (current - verified).total_seconds() / 3600.0
    if age_hours < 0:
        return {
            "state": "UNKNOWN",
            "canonical_freshness": "unknown",
            "age_hours": round(age_hours, 3),
            "analysis_allowed": True,
            "material_execution_allowed": False,
            "reason": "Verification timestamp is in the future.",
        }

    if age_hours <= due_after_hours:
        state = "CURRENT"
        canonical = "current"
        execution = True
        reason = "Source is within the explicit verification window."
    elif age_hours <= stale_after_hours:
        state = "DUE_FOR_REVERIFY"
        canonical = "current"
        execution = True
        reason = "Source remains usable but is due for re-verification."
    else:
        state = "STALE"
        canonical = "stale"
        execution = False
        reason = "Source exceeded the explicit stale threshold."

    return {
        "state": state,
        "canonical_freshness": canonical,
        "age_hours": round(age_hours, 3),
        "analysis_allowed": True,
        "material_execution_allowed": execution,
        "reason": reason,
    }


def assess_regulatory_source(
    source: dict[str, Any],
    *,
    now: str,
    due_after_hours: float,
    stale_after_hours: float,
) -> dict[str, Any]:
    payload = source.get("payload", {})
    assessment = assess_freshness(
        verified_at=payload.get("verified_at"),
        now=now,
        due_after_hours=due_after_hours,
        stale_after_hours=stale_after_hours,
    )
    return {
        "regulatory_source_id": payload.get("regulatory_source_id"),
        "verified_at": payload.get("verified_at"),
        "policy": {
            "due_after_hours": due_after_hours,
            "stale_after_hours": stale_after_hours,
        },
        **assessment,
    }
