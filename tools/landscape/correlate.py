#!/usr/bin/env python3
"""Explainable read-only correlation policies for Landscape Intelligence v0.1."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from normalize import _validator
from reconcile import reconcile


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _finding(
    *,
    finding_id: str,
    finding_type: str,
    adjudication: str,
    severity: str,
    status: str,
    observed_at: str,
    evidence_refs: list[str],
    asset_id: str | None = None,
    confidence: float = 1.0,
) -> dict[str, Any]:
    record = {
        "schema_version": "0.1",
        "record_id": finding_id,
        "record_type": "finding",
        "source": {
            "source_id": "landscape-correlation-policy-v0.1",
            "system": "other",
            "source_type": "derived",
            "location": "tools/landscape/correlate.py",
            "collected_at": observed_at,
            "hash": None,
            "freshness": "current",
            "trust_level": "derived",
        },
        "observed_at": observed_at,
        "payload": {
            "finding_id": finding_id,
            "asset_id": asset_id,
            "type": finding_type,
            "adjudication": adjudication,
            "severity": severity,
            "status": status,
            "evidence_refs": evidence_refs,
            "confidence": confidence,
        },
    }
    _validator().validate(record)
    return record


def _impact(
    *,
    impact_id: str,
    subject_id: str,
    domain: str,
    score: int | str,
    rationale: str,
    observed_at: str,
    confidence: float,
) -> dict[str, Any]:
    record = {
        "schema_version": "0.1",
        "record_id": impact_id,
        "record_type": "impact_assessment",
        "source": {
            "source_id": "landscape-correlation-policy-v0.1",
            "system": "other",
            "source_type": "derived",
            "location": "tools/landscape/correlate.py",
            "collected_at": observed_at,
            "hash": None,
            "freshness": "current",
            "trust_level": "derived",
        },
        "observed_at": observed_at,
        "payload": {
            "impact_id": impact_id,
            "subject_id": subject_id,
            "domain": domain,
            "score": score,
            "rationale": rationale,
            "confidence": confidence,
        },
    }
    _validator().validate(record)
    return record


def correlate(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    findings = list(reconcile(records))
    impacts: list[dict[str, Any]] = []

    # Policy: unknown cost is visibility gap, not zero.
    for record in records:
        if record["record_type"] != "cost_snapshot":
            continue
        payload = record["payload"]
        if payload["amount"] is None or payload["cost_type"] == "unknown":
            fid = f"finding:cost-visibility:{_digest(record['record_id'])}"
            findings.append(
                _finding(
                    finding_id=fid,
                    finding_type="visibility_gap",
                    adjudication="VISIBILITY_GAP",
                    severity="UNKNOWN",
                    status="VISIBILITY_GAP",
                    observed_at=record["observed_at"],
                    evidence_refs=[record["record_id"]],
                    confidence=1.0,
                )
            )
            impacts.append(
                _impact(
                    impact_id=f"impact:{fid}:financial",
                    subject_id=fid,
                    domain="financial",
                    score="UNKNOWN",
                    rationale="Cost is not evidenced; UNKNOWN must not be represented as zero.",
                    observed_at=record["observed_at"],
                    confidence=1.0,
                )
            )

    # Policy: stale/expired authoritative sources create a visibility gap.
    for record in records:
        freshness = record["source"].get("freshness")
        if freshness not in {"stale", "expired"}:
            continue
        fid = f"finding:source-freshness:{_digest(record['source']['source_id'])}"
        findings.append(
            _finding(
                finding_id=fid,
                finding_type="visibility_gap",
                adjudication="VISIBILITY_GAP",
                severity="WARNING",
                status="VISIBILITY_GAP",
                observed_at=record["observed_at"],
                evidence_refs=[record["record_id"]],
                asset_id=record.get("payload", {}).get("asset_id"),
                confidence=1.0,
            )
        )

    # Policy: monitoring health states can raise a risk, but never prescribe FIX.
    unhealthy = {"Degraded", "Unhealthy", "Failed", "Critical"}
    for record in records:
        if record["record_type"] != "observation":
            continue
        payload = record["payload"]
        if payload.get("fact_type") != "health":
            continue
        value = payload.get("value") or {}
        state = value.get("state") or value.get("health")
        if state not in unhealthy:
            continue
        fid = f"finding:health:{_digest([payload.get('asset_id'), state, record['record_id']])}"
        findings.append(
            _finding(
                finding_id=fid,
                finding_type="risk",
                adjudication="PENDING",
                severity="WARNING" if state != "Critical" else "CRITICAL",
                status="OPEN",
                observed_at=record["observed_at"],
                evidence_refs=[record["record_id"]],
                asset_id=payload.get("asset_id"),
                confidence=1.0,
            )
        )
        impacts.append(
            _impact(
                impact_id=f"impact:{fid}:availability",
                subject_id=fid,
                domain="availability",
                score="UNKNOWN",
                rationale="Observed health degradation requires domain assessment before assigning material impact.",
                observed_at=record["observed_at"],
                confidence=1.0,
            )
        )



    # Policy: explicit NoData/Unknown health states are visibility gaps, not healthy zeroes.
    no_data_states = {"NoData", "Unknown", "No Data", "UNKNOWN"}
    for record in records:
        if record["record_type"] != "observation":
            continue
        payload = record["payload"]
        if payload.get("fact_type") != "health":
            continue
        value = payload.get("value") or {}
        state = value.get("state") or value.get("health")
        if state not in no_data_states:
            continue
        fid = f"finding:health-visibility:{_digest([payload.get('asset_id'), state, record['record_id']])}"
        findings.append(
            _finding(
                finding_id=fid,
                finding_type="visibility_gap",
                adjudication="VISIBILITY_GAP",
                severity="UNKNOWN",
                status="VISIBILITY_GAP",
                observed_at=record["observed_at"],
                evidence_refs=[record["record_id"]],
                asset_id=payload.get("asset_id"),
                confidence=1.0,
            )
        )
        impacts.append(
            _impact(
                impact_id=f"impact:{fid}:availability",
                subject_id=fid,
                domain="availability",
                score="UNKNOWN",
                rationale="Source explicitly reports missing/unknown health data; numeric or empty values must not be interpreted as healthy.",
                observed_at=record["observed_at"],
                confidence=1.0,
            )
        )

    # Policy: broad Key Vault secret access is a security case, never an automatic removal.
    for record in records:
        if record["record_type"] != "observation":
            continue
        payload = record["payload"]
        if payload.get("fact_type") != "identity":
            continue
        value = payload.get("value") or {}
        if value.get("role") != "Key Vault Secrets User":
            continue
        if value.get("scope_level") != "vault":
            continue
        fid = f"finding:security-rbac:{_digest([payload.get('asset_id'), value.get('principal_id'), value.get('scope')])}"
        findings.append(
            _finding(
                finding_id=fid,
                finding_type="security",
                adjudication="PENDING",
                severity="WARNING",
                status="OPEN",
                observed_at=record["observed_at"],
                evidence_refs=[record["record_id"]],
                asset_id=payload.get("asset_id"),
                confidence=1.0,
            )
        )
        impacts.append(
            _impact(
                impact_id=f"impact:{fid}:security",
                subject_id=fid,
                domain="security",
                score="UNKNOWN",
                rationale="Broad secret access is visible; functional substitution and blast-radius evidence are required before any removal.",
                observed_at=record["observed_at"],
                confidence=1.0,
            )
        )


    # Policy: active asset without owner is a governance visibility gap.
    for record in records:
        if record["record_type"] != "asset":
            continue
        payload = record["payload"]
        if payload.get("status") != "ACTIVE":
            continue
        if payload.get("owner"):
            continue
        fid = f"finding:missing-owner:{_digest(payload.get('asset_id'))}"
        findings.append(
            _finding(
                finding_id=fid,
                finding_type="governance",
                adjudication="VISIBILITY_GAP",
                severity="INFO",
                status="VISIBILITY_GAP",
                observed_at=record["observed_at"],
                evidence_refs=[record["record_id"]],
                asset_id=payload.get("asset_id"),
                confidence=1.0,
            )
        )

    # Policy: a draft/open PR is evidence only; it never becomes a decision.
    for record in records:
        if record["record_type"] != "observation":
            continue
        payload = record["payload"]
        if payload.get("fact_type") != "state":
            continue
        value = payload.get("value") or {}
        if "pr_number" not in value:
            continue
        if value.get("draft") is True:
            # Deliberately no finding: visibility is preserved without manufacturing risk.
            continue

    # Deduplicate by record id while preserving deterministic ordering.
    unique_findings = {f["record_id"]: f for f in findings}
    unique_impacts = {i["record_id"]: i for i in impacts}
    return {
        "findings": [unique_findings[k] for k in sorted(unique_findings)],
        "impacts": [unique_impacts[k] for k in sorted(unique_impacts)],
    }
