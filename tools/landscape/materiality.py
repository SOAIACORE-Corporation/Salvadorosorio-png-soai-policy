#!/usr/bin/env python3
"""Explicit materiality policies for Landscape Intelligence.

Thresholds are inputs. The engine never invents financial materiality.
"""

from __future__ import annotations

from typing import Any


def evaluate_cost_materiality(
    *,
    previous_amount: float | None,
    current_amount: float | None,
    policy: dict[str, Any] | None,
) -> dict[str, Any]:
    if previous_amount is None or current_amount is None:
        return {
            "state": "UNKNOWN",
            "material": None,
            "reason": "Cost evidence is incomplete.",
            "delta_absolute": None,
            "delta_percent": None,
        }

    delta = current_amount - previous_amount
    pct = None if previous_amount == 0 else (delta / previous_amount) * 100.0

    if not policy:
        return {
            "state": "NO_POLICY",
            "material": None,
            "reason": "No materiality policy supplied; engine will not invent thresholds.",
            "delta_absolute": delta,
            "delta_percent": pct,
        }

    abs_threshold = policy.get("absolute_threshold")
    pct_threshold = policy.get("percent_threshold")

    checks = []
    if abs_threshold is not None:
        checks.append(abs(delta) >= float(abs_threshold))
    if pct_threshold is not None and pct is not None:
        checks.append(abs(pct) >= float(pct_threshold))

    if not checks:
        return {
            "state": "NO_POLICY",
            "material": None,
            "reason": "Policy contains no usable threshold.",
            "delta_absolute": delta,
            "delta_percent": pct,
        }

    material = any(checks) if policy.get("mode", "ANY") == "ANY" else all(checks)
    return {
        "state": "EVALUATED",
        "material": material,
        "reason": "Evaluated only against explicit supplied thresholds.",
        "delta_absolute": delta,
        "delta_percent": pct,
        "policy": policy,
    }
