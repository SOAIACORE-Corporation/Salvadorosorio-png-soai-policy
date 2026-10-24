#!/usr/bin/env python3
"""Deterministic context-continuity confidence for Landscape Intelligence.

The score measures evidentiary continuity. It is not a probability that the
model is "right" and it never substitutes for explicit decision authority.
"""

from __future__ import annotations

from typing import Any


DEFAULT_WEIGHTS = {
    "evidence_coverage": 30,
    "causal_continuity": 25,
    "authority_integrity": 20,
    "freshness": 15,
    "receipt_integrity": 10,
}


def _ratio(confirmed: int, expected: int) -> float:
    if expected < 0 or confirmed < 0 or confirmed > expected:
        raise ValueError("invalid confirmed/expected counts")
    if expected == 0:
        return 1.0
    return confirmed / expected


def _band(score: float) -> str:
    if score >= 95:
        return "VERIFIED_CONTINUITY"
    if score >= 85:
        return "HIGH_CONFIDENCE"
    if score >= 70:
        return "PARTIAL_CONTINUITY"
    if score >= 50:
        return "DEGRADED_CONTINUITY"
    return "UNRELIABLE_CONTINUITY"


def assess_context_integrity(
    *,
    evidence_confirmed: int,
    evidence_expected: int,
    causal_links_confirmed: int,
    causal_links_expected: int,
    authority_confirmed: int,
    authority_expected: int,
    fresh_sources: int,
    required_sources: int,
    receipts_confirmed: int,
    receipts_expected: int,
    missing_material_primary_evidence: bool = False,
    missing_required_authority: bool = False,
    unrecovered_verbatim_dialogue: bool = False,
    weights: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Return a transparent 0..100 continuity score and explicit claim gates.

    Every dimension is computed from auditable counts. Two fail-closed claim
    ceilings prevent a superficially high score from overstating continuity:
    - missing required authority caps claimable confidence at 84;
    - missing primary evidence for a material transition caps it at 69.

    Missing verbatim dialogue is reported but does not by itself reduce the
    score when state, decisions, rationale and receipts are independently
    recoverable.
    """

    weights = dict(weights or DEFAULT_WEIGHTS)
    if set(weights) != set(DEFAULT_WEIGHTS) or sum(weights.values()) != 100:
        raise ValueError("weights must define the five canonical dimensions and sum to 100")

    ratios = {
        "evidence_coverage": _ratio(evidence_confirmed, evidence_expected),
        "causal_continuity": _ratio(causal_links_confirmed, causal_links_expected),
        "authority_integrity": _ratio(authority_confirmed, authority_expected),
        "freshness": _ratio(fresh_sources, required_sources),
        "receipt_integrity": _ratio(receipts_confirmed, receipts_expected),
    }

    raw_score = round(sum(ratios[k] * weights[k] for k in weights), 2)
    claim_ceiling = 100
    gates: list[str] = []

    if missing_required_authority:
        claim_ceiling = min(claim_ceiling, 84)
        gates.append("MISSING_REQUIRED_AUTHORITY")
    if missing_material_primary_evidence:
        claim_ceiling = min(claim_ceiling, 69)
        gates.append("MISSING_MATERIAL_PRIMARY_EVIDENCE")
    if unrecovered_verbatim_dialogue:
        gates.append("VERBATIM_DIALOGUE_UNRECOVERED")

    claimable_score = min(raw_score, float(claim_ceiling))

    return {
        "context_integrity_version": "0.1",
        "raw_score_pct": raw_score,
        "claimable_score_pct": round(claimable_score, 2),
        "confidence_band": _band(claimable_score),
        "dimensions": {
            key: {
                "weight_pct": weights[key],
                "ratio": round(ratios[key], 4),
                "contribution_pct": round(ratios[key] * weights[key], 2),
            }
            for key in weights
        },
        "claim_ceiling_pct": claim_ceiling,
        "gates": gates,
        "semantics": {
            "score_means": "measured evidentiary continuity across required context dimensions",
            "score_does_not_mean": "probability that an AI answer is factually correct",
            "authority_rule": "confidence never grants execution or exception authority",
        },
    }
