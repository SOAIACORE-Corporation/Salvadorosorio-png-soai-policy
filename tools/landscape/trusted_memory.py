#!/usr/bin/env python3
"""Trusted Memory Snapshot, versioned recovery manifest, and fidelity evaluator.

JSON is used as the canonical serialization. JSON documents are also valid
YAML 1.2, so frozen .yaml artifacts can remain dependency-free and be parsed
deterministically with Python's standard library.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


SNAPSHOT_REQUIRED = {
    "snapshot_id", "schema_version", "snapshot_version", "created_at", "status",
    "project", "objective", "checkpoint", "continuity", "error_matrix",
    "metrics", "rules", "authoritative_sources", "evidence_inventory_ref",
    "decisions", "pending_and_exceptions", "resume_point", "content_sha256",
}

CRITICAL_FIELDS = (
    "snapshot_id",
    "objective",
    "checkpoint",
    "rules",
    "pending_and_exceptions",
    "resume_point",
)

FIDELITY_WEIGHTS = {
    "snapshot_identity": 5,
    "objective": 15,
    "scope_and_exclusions": 8,
    "critical_rules": 12,
    "checkpoint_and_version": 10,
    "authoritative_evidence": 12,
    "error_state": 8,
    "metrics": 8,
    "pending_and_exceptions": 10,
    "resume_point": 10,
    "traceability": 2,
}

NULLIFIERS = {
    "OBJECTIVE_MISMATCH",
    "HEAD_MISMATCH",
    "CRITICAL_RULE_LOSS",
    "EXCEPTION_LOSS",
    "FALSE_FUNCTIONAL_SUCCESS",
    "FALSE_CORRELATION_100",
    "MISSING_AS_NEGATIVE_FACT",
    "WRONG_RESUME_PHASE",
    "SNAPSHOT_MIXING",
    "STALE_AS_CURRENT",
    "FALSE_COMPLETE_STATUS",
    "AUTHORITATIVE_SOURCE_MISSING",
    "SNAPSHOT_HASH_MISMATCH",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest().upper()


def _parse_ts(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("timestamp must be a non-empty string")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def seal_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    sealed = deepcopy(snapshot)
    sealed.pop("content_sha256", None)
    sealed["content_sha256"] = sha256_hex(sealed)
    return sealed


def validate_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    missing = sorted(SNAPSHOT_REQUIRED - set(snapshot))
    errors.extend(f"missing:{field}" for field in missing)

    if snapshot.get("status") not in {"CANDIDATE", "APPROVED", "CANONICAL", "FROZEN"}:
        errors.append("invalid_status")

    version_no = snapshot.get("version_no")
    if not isinstance(version_no, int) or version_no < 1:
        errors.append("invalid_version_no")

    try:
        _parse_ts(snapshot.get("created_at"))
    except Exception:
        errors.append("invalid_created_at")

    expected = snapshot.get("content_sha256")
    if expected:
        body = deepcopy(snapshot)
        body.pop("content_sha256", None)
        actual = sha256_hex(body)
        if expected != actual:
            errors.append("content_hash_mismatch")
    else:
        actual = None
        errors.append("missing_content_hash")

    checkpoint = snapshot.get("checkpoint", {})
    head = checkpoint.get("head")
    if not isinstance(head, str) or len(head) != 40:
        errors.append("invalid_checkpoint_head")

    return {
        "valid": not errors,
        "errors": errors,
        "actual_content_sha256": actual,
    }


def validate_manifest(manifest: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    manifest_body = deepcopy(manifest)
    expected_manifest_hash = manifest_body.pop("content_sha256", None)
    actual_manifest_hash = sha256_hex(manifest_body)
    if expected_manifest_hash != actual_manifest_hash:
        errors.append("manifest_hash_mismatch")
    target = manifest.get("target_snapshot", {})
    if target.get("snapshot_id") != snapshot.get("snapshot_id"):
        errors.append("snapshot_id_mismatch")
    if target.get("snapshot_version") != snapshot.get("snapshot_version"):
        errors.append("snapshot_version_mismatch")
    if target.get("expected_hash") != snapshot.get("content_sha256"):
        errors.append("snapshot_hash_mismatch")

    requirements = manifest.get("requirements", [])
    seen: set[str] = set()
    for req in requirements:
        rid = req.get("requirement_id")
        if not rid or rid in seen:
            errors.append("invalid_or_duplicate_requirement_id")
        seen.add(rid)
        if req.get("status") not in {
            "CONFIRMED", "PARTIAL", "MISSING", "STALE", "UNKNOWN", "NOT_APPLICABLE"
        }:
            errors.append(f"invalid_requirement_status:{rid}")

    return {
        "valid": not errors,
        "errors": errors,
        "actual_content_sha256": actual_manifest_hash,
    }


def validate_evidence_inventory(
    manifest: dict[str, Any],
    evidence_inventory: dict[str, Any],
    *,
    objective_id: str,
) -> dict[str, Any]:
    errors: list[str] = []
    inventory_body = deepcopy(evidence_inventory)
    expected_inventory_hash = inventory_body.pop("content_sha256", None)
    actual_inventory_hash = sha256_hex(inventory_body)
    if expected_inventory_hash != actual_inventory_hash:
        errors.append("evidence_inventory_hash_mismatch")

    manifest_inventory = manifest.get("evidence_inventory", {})
    if manifest_inventory.get("inventory_id") != evidence_inventory.get("inventory_id"):
        errors.append("evidence_inventory_id_mismatch")
    if manifest_inventory.get("expected_hash") != evidence_inventory.get("content_sha256"):
        errors.append("evidence_inventory_expected_hash_mismatch")

    evidence = {
        item.get("evidence_id"): item
        for item in evidence_inventory.get("evidence", [])
        if item.get("evidence_id")
    }

    for req in manifest.get("requirements", []):
        rid = req.get("requirement_id")
        status = req.get("status")
        ids = req.get("evidence_ids", [])

        if status == "CONFIRMED" and not ids:
            errors.append(f"confirmed_without_evidence:{rid}")

        for eid in ids:
            item = evidence.get(eid)
            if item is None:
                errors.append(f"missing_evidence_item:{rid}:{eid}")
                continue

            if item.get("objective_id") not in {None, objective_id}:
                errors.append(f"evidence_objective_mismatch:{rid}:{eid}")

            quality = item.get("quality")
            if status == "CONFIRMED" and quality != "CONFIRMED":
                errors.append(f"confirmed_requirement_uses_{quality}:{rid}:{eid}")

            if item.get("freshness") == "STALE" and status == "CONFIRMED":
                errors.append(f"stale_evidence_as_current:{rid}:{eid}")

    return {
        "valid": not errors,
        "errors": errors,
        "actual_content_sha256": actual_inventory_hash,
    }


def recovery_decision(manifest: dict[str, Any]) -> dict[str, Any]:
    requirements = manifest.get("requirements", [])
    blocking = []
    partial = []
    for req in requirements:
        status = req.get("status")
        criticality = req.get("criticality")
        if criticality == "critical" and status != "CONFIRMED":
            blocking.append(req.get("requirement_id"))
        elif criticality == "necessary" and status != "CONFIRMED":
            partial.append(req.get("requirement_id"))

    if blocking:
        result = "RECOVERY_BLOCKED"
    elif partial:
        result = "RECOVERABLE_WITH_EXCEPTIONS"
    else:
        complementary_missing = any(
            req.get("criticality") == "complementary"
            and req.get("status") != "CONFIRMED"
            for req in requirements
        )
        result = "RECOVERABLE_WITH_EXCEPTIONS" if complementary_missing else "RECOVERABLE"

    return {
        "result": result,
        "blocking_requirement_ids": sorted(x for x in blocking if x),
        "exception_requirement_ids": sorted(x for x in partial if x),
    }


def reconstruct_from_snapshot(
    snapshot: dict[str, Any],
    manifest: dict[str, Any],
    evidence_inventory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sv = validate_snapshot(snapshot)
    mv = validate_manifest(manifest, snapshot)
    decision = recovery_decision(manifest)
    ev = (
        validate_evidence_inventory(
            manifest,
            evidence_inventory,
            objective_id=snapshot["objective"]["objective_id"],
        )
        if evidence_inventory is not None
        else {"valid": True, "errors": []}
    )
    if (
        not sv["valid"]
        or not mv["valid"]
        or not ev["valid"]
        or decision["result"] == "RECOVERY_BLOCKED"
    ):
        raise ValueError(
            "trusted recovery prerequisites not satisfied: "
            + ", ".join(sv["errors"] + mv["errors"] + ev["errors"])
        )

    return {
        "snapshot_id": snapshot["snapshot_id"],
        "objective": deepcopy(snapshot["objective"]),
        "project": deepcopy(snapshot["project"]),
        "checkpoint": deepcopy(snapshot["checkpoint"]),
        "continuity": deepcopy(snapshot["continuity"]),
        "error_matrix": deepcopy(snapshot["error_matrix"]),
        "metrics": deepcopy(snapshot["metrics"]),
        "rules": deepcopy(snapshot["rules"]),
        "authoritative_sources": deepcopy(snapshot["authoritative_sources"]),
        "decisions": deepcopy(snapshot["decisions"]),
        "pending_and_exceptions": deepcopy(snapshot["pending_and_exceptions"]),
        "resume_point": deepcopy(snapshot["resume_point"]),
        "recovery_status": decision["result"],
    }


def _exact(reference: Any, recovered: Any) -> bool:
    return _canonical(reference) == _canonical(recovered)


def detect_nullifiers(reference: dict[str, Any], recovered: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    if not _exact(reference.get("objective"), recovered.get("objective")):
        failures.append("OBJECTIVE_MISMATCH")

    ref_head = reference.get("checkpoint", {}).get("head")
    got_head = recovered.get("checkpoint", {}).get("head")
    if ref_head != got_head:
        failures.append("HEAD_MISMATCH")

    if not _exact(reference.get("rules"), recovered.get("rules")):
        failures.append("CRITICAL_RULE_LOSS")

    ref_exc = reference.get("pending_and_exceptions", {}).get("exceptions", [])
    got_exc = recovered.get("pending_and_exceptions", {}).get("exceptions", [])
    if not _exact(ref_exc, got_exc):
        failures.append("EXCEPTION_LOSS")

    functional = recovered.get("pending_and_exceptions", {}).get(
        "functional_endpoint_validation", {}
    )
    if functional.get("status") in {"CONFIRMED", "SUCCESS", "DEMONSTRATED"}:
        failures.append("FALSE_FUNCTIONAL_SUCCESS")

    correlation = recovered.get("metrics", {}).get("correlation_integrity", {})
    if correlation.get("denominator") == 0 and correlation.get("result_pct") == 100:
        failures.append("FALSE_CORRELATION_100")

    if recovered.get("resume_point", {}).get("phase") != reference.get(
        "resume_point", {}
    ).get("phase"):
        failures.append("WRONG_RESUME_PHASE")

    if recovered.get("objective", {}).get("scope_status") == "COMPLETED":
        if reference.get("objective", {}).get("scope_status") == "COMPLETED_WITH_EXCEPTIONS":
            failures.append("FALSE_COMPLETE_STATUS")

    if not recovered.get("authoritative_sources"):
        failures.append("AUTHORITATIVE_SOURCE_MISSING")

    return sorted(set(failures))


def fidelity_score(reference: dict[str, Any], recovered: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "snapshot_identity": reference.get("snapshot_id") == recovered.get("snapshot_id"),
        "objective": _exact(reference.get("objective"), recovered.get("objective")),
        "scope_and_exclusions": _exact(
            reference.get("objective", {}).get("scope"),
            recovered.get("objective", {}).get("scope"),
        ) and _exact(
            reference.get("objective", {}).get("exclusions"),
            recovered.get("objective", {}).get("exclusions"),
        ),
        "critical_rules": _exact(reference.get("rules"), recovered.get("rules")),
        "checkpoint_and_version": _exact(
            reference.get("checkpoint"), recovered.get("checkpoint")
        ),
        "authoritative_evidence": _exact(
            reference.get("authoritative_sources"),
            recovered.get("authoritative_sources"),
        ),
        "error_state": _exact(
            reference.get("error_matrix"), recovered.get("error_matrix")
        ),
        "metrics": _exact(reference.get("metrics"), recovered.get("metrics")),
        "pending_and_exceptions": _exact(
            reference.get("pending_and_exceptions"),
            recovered.get("pending_and_exceptions"),
        ),
        "resume_point": _exact(
            reference.get("resume_point"), recovered.get("resume_point")
        ),
        "traceability": bool(recovered.get("authoritative_sources"))
        and bool(recovered.get("checkpoint", {}).get("head")),
    }

    points = sum(FIDELITY_WEIGHTS[key] for key, passed in checks.items() if passed)
    nullifiers = detect_nullifiers(reference, recovered)
    critical_ok = all(_exact(reference.get(field), recovered.get(field)) for field in CRITICAL_FIELDS)

    passed = points >= 98 and not nullifiers and critical_ok
    return {
        "structural_score": points,
        "semantic_score": points,
        "total_score": points,
        "max_score": 100,
        "checks": checks,
        "invalidating_conditions": nullifiers,
        "critical_fields_preserved": critical_ok,
        "result": "PASS" if passed else "FAIL",
    }


def compare_snapshot_versions(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    if previous.get("snapshot_id") == current.get("snapshot_id"):
        raise ValueError("snapshot versions must have distinct immutable IDs")

    changed = [
        key for key in sorted(set(previous) | set(current))
        if key not in {"content_sha256"} and not _exact(previous.get(key), current.get(key))
    ]

    return {
        "diff_version": "1.0",
        "previous_snapshot_id": previous.get("snapshot_id"),
        "current_snapshot_id": current.get("snapshot_id"),
        "previous_hash": previous.get("content_sha256"),
        "current_hash": current.get("content_sha256"),
        "changed_fields": changed,
        "unchanged": not changed,
    }


def persist_dual(
    snapshot: dict[str, Any],
    primary_path: Path,
    secondary_path: Path,
) -> dict[str, Any]:
    validation = validate_snapshot(snapshot)
    if not validation["valid"]:
        raise ValueError("invalid snapshot: " + ", ".join(validation["errors"]))

    if primary_path.resolve() == secondary_path.resolve():
        raise ValueError("primary and secondary paths must differ")

    payload = json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n"
    for path in (primary_path, secondary_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(str(path))
        path.write_text(payload, encoding="utf-8")

    return {
        "primary": str(primary_path),
        "secondary": str(secondary_path),
        "content_sha256": snapshot["content_sha256"],
        "same_content": primary_path.read_bytes() == secondary_path.read_bytes(),
    }


def postgres_projection(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Map a trusted snapshot onto the existing A2 bitemporal model.

    No database write is performed.
    """
    validation = validate_snapshot(snapshot)
    if not validation["valid"]:
        raise ValueError("cannot project invalid trusted snapshot")

    return {
        "canonical_memory": {
            "memory_id": snapshot["snapshot_id"],
            "logical_memory_id": snapshot["logical_snapshot_id"],
            "version_no": snapshot["version_no"],
            "project_scope": snapshot["project"]["name"],
            "subject_ref": snapshot["objective"]["objective_id"],
            "content": {
                "objective": snapshot["objective"],
                "rules": snapshot["rules"],
                "decisions": snapshot["decisions"],
                "pending_and_exceptions": snapshot["pending_and_exceptions"],
                "resume_point": snapshot["resume_point"],
            },
            "epistemic_class": "CONFIRMED_CONTEXT",
            "admission_state": "ADMITTED",
            "observed_time": snapshot["created_at"],
            "valid_from": snapshot["valid_from"],
            "valid_until": snapshot.get("valid_until"),
            "supersedes_memory_id": snapshot.get("previous_snapshot_id"),
            "receipt_ref": snapshot.get("metadata", {}).get("receipt_ref"),
            "metadata": {
                "content_sha256": snapshot["content_sha256"],
                "checkpoint_head": snapshot["checkpoint"]["head"],
            },
        },
        "operational_state": {
            "state_id": snapshot["snapshot_id"] + ":state",
            "state_key": snapshot["logical_snapshot_id"],
            "version_no": snapshot["version_no"],
            "project_scope": snapshot["project"]["name"],
            "status": snapshot["objective"]["scope_status"],
            "phase": snapshot["resume_point"]["phase"],
            "decision": snapshot["resume_point"]["next_objective"],
            "source_authority": "TRUSTED_MEMORY_SNAPSHOT",
            "source_ref": snapshot["checkpoint"]["head"],
            "observed_time": snapshot["created_at"],
            "valid_from": snapshot["valid_from"],
            "valid_until": snapshot.get("valid_until"),
            "supersedes_state_id": (
                snapshot.get("previous_snapshot_id") + ":state"
                if snapshot.get("previous_snapshot_id")
                else None
            ),
            "receipt_ref": snapshot.get("metadata", {}).get("receipt_ref"),
            "metadata": {
                "snapshot_id": snapshot["snapshot_id"],
                "content_sha256": snapshot["content_sha256"],
            },
        },
    }
