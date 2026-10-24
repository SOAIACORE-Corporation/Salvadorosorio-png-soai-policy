#!/usr/bin/env python3
"""Identity visibility checks for canonical asset records."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def identity_aliases(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names: dict[str, set[str]] = defaultdict(set)
    for record in records:
        if record.get("record_type") != "asset":
            continue
        payload = record.get("payload", {})
        asset_id = payload.get("asset_id")
        name = payload.get("name")
        if asset_id and name:
            names[asset_id].add(name)

    result = []
    for asset_id, aliases in sorted(names.items()):
        if len(aliases) > 1:
            result.append({
                "pattern_type":"ASSET_ALIAS_SET",
                "subject_id":asset_id,
                "aliases":sorted(aliases),
                "confidence":1.0,
                "interpretation":"Multiple display names map to one canonical asset identity; do not create duplicate assets.",
            })
    return result
