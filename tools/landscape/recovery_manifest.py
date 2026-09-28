#!/usr/bin/env python3
"""Evidence-inventory driven context recovery assessment."""

from __future__ import annotations

from typing import Any

from context_integrity import assess_context_integrity


DIMENSIONS = {
    "evidence_coverage",
    "causal_continuity",
    "authority_integrity",
    "freshness",
    "receipt_integrity",
}


def assess_recovery_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    items = manifest.get("requirements")
    if not isinstance(items, list):
        raise ValueError("manifest.requirements must be a list")

    counts = {d: {"expected": 0, "confirmed": 0} for d in DIMENSIONS}
    missing_material_primary = False
    missing_required_authority = False

    for item in items:
        dimension = item.get("dimension")
        if dimension not in DIMENSIONS:
            raise ValueError(f"unsupported dimension: {dimension}")
        if item.get("required", True) is not True:
            continue

        counts[dimension]["expected"] += 1
        status = item.get("status")
        if status == "CONFIRMED":
            counts[dimension]["confirmed"] += 1
        elif status not in {"MISSING", "STALE", "PARTIAL", "UNKNOWN"}:
            raise ValueError(f"unsupported requirement status: {status}")

        if (
            dimension == "evidence_coverage"
            and item.get("material_primary") is True
            and status != "CONFIRMED"
        ):
            missing_material_primary = True

        if (
            dimension == "authority_integrity"
            and item.get("required_authority") is True
            and status != "CONFIRMED"
        ):
            missing_required_authority = True

    result = assess_context_integrity(
        evidence_confirmed=counts["evidence_coverage"]["confirmed"],
        evidence_expected=counts["evidence_coverage"]["expected"],
        causal_links_confirmed=counts["causal_continuity"]["confirmed"],
        causal_links_expected=counts["causal_continuity"]["expected"],
        authority_confirmed=counts["authority_integrity"]["confirmed"],
        authority_expected=counts["authority_integrity"]["expected"],
        fresh_sources=counts["freshness"]["confirmed"],
        required_sources=counts["freshness"]["expected"],
        receipts_confirmed=counts["receipt_integrity"]["confirmed"],
        receipts_expected=counts["receipt_integrity"]["expected"],
        missing_material_primary_evidence=missing_material_primary,
        missing_required_authority=missing_required_authority,
        unrecovered_verbatim_dialogue=bool(manifest.get("verbatim_dialogue_unrecovered", False)),
    )
    result["recovery_manifest_version"] = manifest.get("recovery_manifest_version", "0.1")
    result["requirement_counts"] = counts
    result["unconfirmed_requirement_ids"] = sorted(
        str(i.get("requirement_id"))
        for i in items
        if i.get("required", True) is True and i.get("status") != "CONFIRMED"
    )
    return result
