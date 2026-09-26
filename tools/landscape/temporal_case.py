#!/usr/bin/env python3
"""Committee-ready cases from explainable temporal patterns."""

from __future__ import annotations

from typing import Any


def temporal_decision_cases(patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases = []
    for pattern in patterns:
        ptype = pattern["pattern_type"]
        subject = pattern["subject_id"]

        if ptype == "PERSISTENT_FINDING":
            alternatives = [
                {"option_id":"MAINTAIN","label":"Mantener estado y seguimiento"},
                {"option_id":"INVESTIGATE","label":"Analizar causa de persistencia"},
                {"option_id":"PREPARE_CHANGE","label":"Preparar propuesta de resolución controlada"},
            ]
        elif ptype == "REPEATED_VISIBILITY_GAP":
            alternatives = [
                {"option_id":"ACCEPT_GAP","label":"Aceptar explícitamente el gap de visibilidad"},
                {"option_id":"CLOSE_GAP","label":"Incorporar o reparar la fuente faltante"},
            ]
        elif ptype == "MONOTONIC_COST_INCREASE":
            alternatives = [
                {"option_id":"OBSERVE","label":"Mantener observación hasta contar con materialidad definida"},
                {"option_id":"DEFINE_MATERIALITY","label":"Definir criterio financiero explícito"},
                {"option_id":"INVESTIGATE_DRIVERS","label":"Analizar drivers de costo sin asumir incidente"},
            ]
        else:
            alternatives = [{"option_id":"INVESTIGATE","label":"Analizar patrón"}]

        cases.append({
            "decision_case_version":"0.1",
            "case_id":f"temporal-case:{ptype}:{subject}",
            "pattern":pattern,
            "decision_required":True,
            "alternatives":alternatives,
            "authority":{
                "ai_role":"ANALYZE_AND_RECOMMEND_ONLY",
                "decision_owner":"OWNER_REQUIRED",
                "execution_authority":"SEPARATE_APPROVAL_REQUIRED",
                "exception_authority":"SOA / Salvador Osorio Ayala",
            },
        })
    return cases
