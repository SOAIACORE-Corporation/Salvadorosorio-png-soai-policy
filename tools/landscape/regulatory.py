"""Regulatory Canonical Layer for SOAiaCore Landscape Intelligence.

The layer supports continuous reasoning while separating regulatory freshness
from execution authority. External binding obligations cannot be waived by an
internal exception authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from authority import is_exception_authority
from normalize import _validator


def regulatory_source_record(raw: dict[str, Any]) -> dict[str, Any]:
    required = (
        "regulatory_source_id","jurisdiction","authority","instrument_type",
        "citation","binding_level","status","official_url","source_tier",
        "verified_at","freshness","exception_mode",
    )
    missing=[k for k in required if raw.get(k) is None]
    if missing:
        raise ValueError(f"regulatory source missing required fields: {', '.join(missing)}")
    record={
        "schema_version":"0.1",
        "record_id":raw["regulatory_source_id"],
        "record_type":"regulatory_source",
        "source":{
            "source_id":raw.get("collector_source_id","regulatory-canon"),
            "system":"other",
            "source_type":"api" if "MACHINE_READABLE" in raw["source_tier"] else "file",
            "location":raw["official_url"],
            "collected_at":raw["verified_at"],
            "hash":raw.get("hash"),
            "freshness":raw["freshness"],
            "trust_level":"authoritative" if raw["source_tier"].startswith(("TIER_1","TIER_2")) else "supporting",
        },
        "observed_at":raw["verified_at"],
        "payload":{
            "regulatory_source_id":raw["regulatory_source_id"],
            "jurisdiction":raw["jurisdiction"],
            "authority":raw["authority"],
            "instrument_type":raw["instrument_type"],
            "citation":raw["citation"],
            "title":raw.get("title"),
            "binding_level":raw["binding_level"],
            "status":raw["status"],
            "effective_from":raw.get("effective_from"),
            "effective_to":raw.get("effective_to"),
            "official_url":raw["official_url"],
            "source_tier":raw["source_tier"],
            "verified_at":raw["verified_at"],
            "freshness":raw["freshness"],
            "hash":raw.get("hash"),
            "exception_mode":raw["exception_mode"],
        }
    }
    _validator().validate(record)
    return record


def regulatory_assertion_record(raw: dict[str, Any], *, observed_at: str) -> dict[str, Any]:
    record={
        "schema_version":"0.1",
        "record_id":raw["assertion_id"],
        "record_type":"regulatory_assertion",
        "source":{
            "source_id":"regulatory-assertion-engine-v0.1",
            "system":"other",
            "source_type":"derived",
            "location":"tools/landscape/regulatory.py",
            "collected_at":observed_at,
            "hash":None,
            "freshness":"current",
            "trust_level":"derived",
        },
        "observed_at":observed_at,
        "payload":{
            "assertion_id":raw["assertion_id"],
            "claim":raw["claim"],
            "regulatory_source_ids":raw["regulatory_source_ids"],
            "jurisdiction":raw["jurisdiction"],
            "binding_level":raw["binding_level"],
            "interpretation":raw["interpretation"],
            "confidence":float(raw["confidence"]),
            "legal_review_required":bool(raw["legal_review_required"]),
        }
    }
    _validator().validate(record)
    return record


def applicability_record(raw: dict[str, Any], *, observed_at: str) -> dict[str, Any]:
    record={
        "schema_version":"0.1",
        "record_id":raw["assessment_id"],
        "record_type":"applicability_assessment",
        "source":{
            "source_id":"regulatory-applicability-engine-v0.1",
            "system":"other",
            "source_type":"derived",
            "location":"tools/landscape/regulatory.py",
            "collected_at":observed_at,
            "hash":None,
            "freshness":"current",
            "trust_level":"derived",
        },
        "observed_at":observed_at,
        "payload":{
            "assessment_id":raw["assessment_id"],
            "scenario_id":raw["scenario_id"],
            "assertion_id":raw["assertion_id"],
            "applies":raw["applies"],
            "reason":raw["reason"],
            "confidence":float(raw["confidence"]),
            "decision_state":raw["decision_state"],
        }
    }
    _validator().validate(record)
    return record


def can_internal_exception_override(source: dict[str, Any], authority: str | None) -> bool:
    payload=source["payload"]
    if payload["exception_mode"]=="NON_WAIVABLE_EXTERNAL":
        return False
    return is_exception_authority(authority)


def regulatory_execution_gate(
    required_sources: list[dict[str, Any]],
    *,
    material_action: bool,
) -> dict[str, Any]:
    if not required_sources:
        return {
            "analysis_allowed":True,
            "execution_allowed":False if material_action else True,
            "state":"REGULATORY_VISIBILITY_GAP",
            "reason":"No regulatory basis supplied.",
        }

    stale=[
        s["payload"]["regulatory_source_id"]
        for s in required_sources
        if s["payload"]["freshness"]!="current"
        or s["payload"]["status"] in {"SUPERSEDED","DRAFT","UNKNOWN"}
    ]
    if stale:
        return {
            "analysis_allowed":True,
            "execution_allowed":False if material_action else True,
            "state":"REGULATORY_REVIEW_REQUIRED",
            "reason":"One or more required regulatory sources are not current/active.",
            "source_ids":stale,
        }

    return {
        "analysis_allowed":True,
        "execution_allowed":True,
        "state":"REGULATORY_BASIS_CURRENT",
        "reason":"Required regulatory sources are current enough for downstream control evaluation.",
        "source_ids":[s["payload"]["regulatory_source_id"] for s in required_sources],
    }
