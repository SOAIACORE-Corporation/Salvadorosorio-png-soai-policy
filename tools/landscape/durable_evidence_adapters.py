#!/usr/bin/env python3
"""Normalize heterogeneous durable sources into evidence inventory items."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


SUPPORTED_SOURCE_KINDS = {"git_commit", "ci_run", "receipt", "snapshot", "decision"}


def _parse_time(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("timestamp must be a non-empty ISO-8601 string")
    normalized = value.replace("Z", "+00:00")
    result = datetime.fromisoformat(normalized)
    if result.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return result.astimezone(timezone.utc)


def _freshness(source: dict[str, Any], *, as_of: str | None) -> bool | None:
    max_age = source.get("freshness_max_age_seconds")
    observed_at = source.get("observed_at")
    if max_age is None or observed_at is None:
        return None
    if not isinstance(max_age, int) or max_age < 0:
        raise ValueError("freshness_max_age_seconds must be a non-negative integer")
    if as_of is None:
        raise ValueError("as_of is required when freshness_max_age_seconds is declared")
    age = (_parse_time(as_of) - _parse_time(observed_at)).total_seconds()
    return 0 <= age <= max_age


def _source_completeness(source: dict[str, Any]) -> str:
    kind = source["source_kind"]
    if source.get("retrieved", True) is not True:
        return "UNKNOWN"

    if kind == "git_commit":
        return "CONFIRMED" if source.get("sha") else "PARTIAL"
    if kind == "ci_run":
        if not source.get("run_id"):
            return "PARTIAL"
        return "CONFIRMED" if source.get("status") == "completed" else "PARTIAL"
    if kind == "receipt":
        return "CONFIRMED" if source.get("receipt_id") or source.get("path") else "PARTIAL"
    if kind == "snapshot":
        return "CONFIRMED" if source.get("snapshot_id") and source.get("content_hash") else "PARTIAL"
    if kind == "decision":
        if not source.get("decision_id"):
            return "PARTIAL"
        return "CONFIRMED" if source.get("authority") else "PARTIAL"

    raise ValueError(f"unsupported source_kind: {kind}")


def adapt_source(source: dict[str, Any], *, as_of: str | None = None) -> dict[str, Any]:
    kind = source.get("source_kind")
    if kind not in SUPPORTED_SOURCE_KINDS:
        raise ValueError(f"unsupported source_kind: {kind}")

    source_id = source.get("source_id")
    requirement_id = source.get("requirement_id")
    if not isinstance(source_id, str) or not source_id:
        raise ValueError("source_id is required")
    if not isinstance(requirement_id, str) or not requirement_id:
        raise ValueError("requirement_id must be explicitly bound by policy/extractor")

    retrieved = source.get("retrieved", True)
    if not isinstance(retrieved, bool):
        raise ValueError("retrieved must be boolean")

    status = _source_completeness(source)
    fresh = _freshness(source, as_of=as_of)

    evidence = {
        "evidence_id": source_id,
        "requirement_id": requirement_id,
        "available": retrieved,
        "validation_status": status,
        "source_ref": source.get("source_ref", source_id),
        "source_kind": kind,
        "source_outcome": source.get("outcome"),
    }
    if fresh is not None:
        evidence["fresh"] = fresh
    return evidence


def adapt_sources(
    sources: list[dict[str, Any]],
    *,
    as_of: str | None = None,
) -> list[dict[str, Any]]:
    return [adapt_source(source, as_of=as_of) for source in sources]
