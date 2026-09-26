#!/usr/bin/env python3
"""Committee-ready Decision Case projection for Landscape Intelligence.

This is a read-only presentation layer. It assembles evidence, impacts, cost,
dependencies and non-ranked alternatives. It never chooses or executes.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _by_type(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        result[record["record_type"]].append(record)
    return result


def _alternatives(finding: dict[str, Any]) -> list[dict[str, Any]]:
    p = finding["payload"]
    ftype = p["type"]
    adjudication = p["adjudication"]

    options = [
        {
            "option_id": "MAINTAIN",
            "label": "Mantener estado actual",
            "preconditions": ["Riesgo residual explícito", "Owner/autoridad identificados"],
            "effect": "No material change",
        }
    ]
    if ftype == "visibility_gap" or adjudication == "VISIBILITY_GAP":
        options.append({
            "option_id": "CLOSE_VISIBILITY_GAP",
            "label": "Obtener evidencia faltante",
            "preconditions": ["Definir fuente factual", "Definir criterio de cierre"],
            "effect": "Improve decision quality without changing production",
        })
    else:
        options.append({
            "option_id": "INVESTIGATE",
            "label": "Ampliar análisis antes de decidir",
            "preconditions": ["Conservar estado PENDING/HOLD", "Capturar evidencia adicional"],
            "effect": "Reduce uncertainty",
        })
        options.append({
            "option_id": "PREPARE_CHANGE",
            "label": "Preparar propuesta de cambio controlado",
            "preconditions": ["Decision Record aprobado", "Precheck", "Rollback", "Validación definida"],
            "effect": "No execution until separately authorized",
        })
    return options


def build_decision_cases(
    records: list[dict[str, Any]],
    *,
    findings: list[dict[str, Any]],
    impacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    typed = _by_type(records)
    impacts_by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for impact in impacts:
        impacts_by_subject[impact["payload"]["subject_id"]].append(impact)

    dependencies = typed.get("dependency", [])
    costs = typed.get("cost_snapshot", [])

    cases = []
    for finding in sorted(findings, key=lambda f: f["record_id"]):
        p = finding["payload"]
        fid = p["finding_id"]
        asset_id = p.get("asset_id")

        related_dependencies = [
            d for d in dependencies
            if d["payload"]["from_id"] in {fid, asset_id}
            or d["payload"]["to_id"] in {fid, asset_id}
        ]
        related_costs = [
            c for c in costs
            if c["payload"]["scope_id"] in {fid, asset_id, "SOAiaCore"}
        ]

        cases.append({
            "decision_case_version": "0.1",
            "case_id": f"case:{fid}",
            "decision_required": True,
            "finding": {
                "finding_id": fid,
                "type": p["type"],
                "adjudication": p["adjudication"],
                "severity": p["severity"],
                "status": p["status"],
                "confidence": p["confidence"],
                "asset_id": asset_id,
            },
            "evidence_refs": list(p.get("evidence_refs", [])),
            "impacts": [
                i["payload"] for i in sorted(
                    impacts_by_subject.get(fid, []), key=lambda x: x["record_id"]
                )
            ],
            "cost_context": [
                c["payload"] for c in sorted(related_costs, key=lambda x: x["record_id"])
            ],
            "dependencies": [
                d["payload"] for d in sorted(related_dependencies, key=lambda x: x["record_id"])
            ],
            "alternatives": _alternatives(finding),
            "authority": {
                "decision_owner": "UNASSIGNED" if not asset_id else "OWNER_REQUIRED",
                "ai_role": "ANALYZE_AND_RECOMMEND_ONLY",
                "execution_authority": "SEPARATE_APPROVAL_REQUIRED",
            },
        })
    return cases
