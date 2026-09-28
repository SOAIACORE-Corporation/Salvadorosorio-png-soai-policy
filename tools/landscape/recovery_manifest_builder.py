#!/usr/bin/env python3
"""Build a Recovery Manifest from declared requirements and durable evidence."""

from __future__ import annotations
from copy import deepcopy
from typing import Any
from recovery_manifest import DIMENSIONS

CANONICAL_REQUIREMENTS = [
    {"requirement_id":"primary-state","dimension":"evidence_coverage","required":True,"material_primary":True},
    {"requirement_id":"causal-link","dimension":"causal_continuity","required":True},
    {"requirement_id":"decision-authority","dimension":"authority_integrity","required":True,"required_authority":True},
    {"requirement_id":"source-freshness","dimension":"freshness","required":True},
    {"requirement_id":"validation-receipt","dimension":"receipt_integrity","required":True},
]
VALID_EVIDENCE_STATUS = {"CONFIRMED","PARTIAL","UNKNOWN"}

def _validate_requirements(requirements: list[dict[str, Any]]) -> None:
    ids=set()
    for requirement in requirements:
        rid=requirement.get("requirement_id")
        if not isinstance(rid,str) or not rid:
            raise ValueError("every requirement requires a non-empty requirement_id")
        if rid in ids:
            raise ValueError(f"duplicate requirement_id: {rid}")
        ids.add(rid)
        if requirement.get("dimension") not in DIMENSIONS:
            raise ValueError(f"unsupported dimension: {requirement.get('dimension')}")

def _validate_evidence(evidence: list[dict[str, Any]]) -> None:
    ids=set()
    for item in evidence:
        eid=item.get("evidence_id")
        if not isinstance(eid,str) or not eid:
            raise ValueError("every evidence item requires a non-empty evidence_id")
        if eid in ids:
            raise ValueError(f"duplicate evidence_id: {eid}")
        ids.add(eid)
        if not isinstance(item.get("requirement_id"),str):
            raise ValueError("every evidence item requires requirement_id")
        if not isinstance(item.get("available"),bool):
            raise ValueError("every evidence item requires boolean available")
        status=item.get("validation_status","UNKNOWN")
        if status not in VALID_EVIDENCE_STATUS:
            raise ValueError(f"unsupported evidence validation_status: {status}")
        if "fresh" in item and item["fresh"] is not None and not isinstance(item["fresh"],bool):
            raise ValueError("fresh must be boolean or null")

def _derive_status(requirement: dict[str, Any], evidence: list[dict[str, Any]]) -> str:
    available=[item for item in evidence if item["available"]]
    if not available:
        return "MISSING"
    statuses={item.get("validation_status","UNKNOWN") for item in available}
    if "UNKNOWN" in statuses:
        return "UNKNOWN"
    if "PARTIAL" in statuses:
        return "PARTIAL"
    if requirement["dimension"]=="freshness":
        freshness=[item.get("fresh") for item in available]
        if any(value is None for value in freshness):
            return "UNKNOWN"
        if any(value is False for value in freshness):
            return "STALE"
    return "CONFIRMED"

def build_recovery_manifest(
    evidence: list[dict[str, Any]],
    *,
    requirements: list[dict[str, Any]] | None = None,
    verbatim_dialogue_unrecovered: bool = False,
) -> dict[str, Any]:
    requirements=deepcopy(requirements or CANONICAL_REQUIREMENTS)
    evidence=deepcopy(evidence)
    _validate_requirements(requirements)
    _validate_evidence(evidence)
    known={r["requirement_id"] for r in requirements}
    unknown=sorted({item["requirement_id"] for item in evidence}-known)
    if unknown:
        raise ValueError("evidence targets undeclared requirements: "+", ".join(unknown))
    generated=[]
    for requirement in requirements:
        rid=requirement["requirement_id"]
        matched=[item for item in evidence if item["requirement_id"]==rid]
        record=dict(requirement)
        record["status"]=_derive_status(requirement,matched)
        record["evidence_ids"]=sorted(item["evidence_id"] for item in matched if item["available"])
        record["source_refs"]=sorted({str(item["source_ref"]) for item in matched if item["available"] and item.get("source_ref")})
        generated.append(record)
    return {
        "recovery_manifest_version":"0.2",
        "generated_from_durable_evidence":True,
        "verbatim_dialogue_unrecovered":bool(verbatim_dialogue_unrecovered),
        "requirements":generated,
        "evidence_inventory_count":len(evidence),
        "evidence_inventory_ids":sorted(item["evidence_id"] for item in evidence),
        "semantics":{
            "policy_rule":"Requirements define what must exist; observed evidence cannot redefine obligations.",
            "absence_rule":"No available evidence for a required item becomes MISSING.",
            "freshness_rule":"Stale evidence remains visible as STALE and is never promoted to current.",
            "authority_rule":"Generated status never grants execution or exception authority.",
        },
    }
