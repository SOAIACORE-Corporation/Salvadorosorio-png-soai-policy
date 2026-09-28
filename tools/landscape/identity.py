"""Canonical identity helpers for Landscape Intelligence.

Identity is deterministic and independent of display names. Helpers are pure
functions and perform no I/O.
"""

from __future__ import annotations


def azure_asset_id(subscription_id: str, resource_id: str) -> str:
    subscription_id = subscription_id.strip()
    resource_id = resource_id.strip()
    if not subscription_id or not resource_id:
        raise ValueError("subscription_id and resource_id are required")
    return f"azure:{subscription_id}:{resource_id}"


def normalize_azure_resource_id(resource_id: str) -> str:
    value = resource_id.strip()
    if not value:
        raise ValueError("resource_id is required")
    return value.rstrip("/")


def same_asset_id(left: str, right: str) -> bool:
    return left.strip() == right.strip()
