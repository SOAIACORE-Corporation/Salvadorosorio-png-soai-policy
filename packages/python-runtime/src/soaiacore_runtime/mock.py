from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import contract_error
from .hashing import sha256_json


def load_mock_fixture(fixture_dir: Path, fixture_id: str) -> dict[str, Any]:
    if not fixture_id or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for character in fixture_id):
        raise contract_error(
            "MOCK_FIXTURE_INVALID",
            "Mock fixture identifier is invalid",
            "EXECUTION",
        )
    path = (fixture_dir / f"{fixture_id}.json").resolve()
    if path.parent != fixture_dir.resolve() or not path.is_file():
        raise contract_error(
            "MOCK_FIXTURE_NOT_FOUND",
            f"Versioned mock fixture {fixture_id} does not exist",
            "EXECUTION",
            status_code=422,
        )
    fixture = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "fixture_id",
        "fixture_version",
        "created_at",
        "claim",
        "graph_relation_type",
        "tool_name",
    }
    if required.difference(fixture) or fixture["fixture_id"] != fixture_id:
        raise contract_error(
            "MOCK_FIXTURE_INVALID",
            "Mock fixture is incomplete or has a mismatched identifier",
            "EXECUTION",
        )
    fixture["fixture_hash"] = sha256_json(fixture)
    return fixture


def deterministic_embedding(seed_hash: str, dimensions: int = 8) -> list[float]:
    raw = bytes.fromhex(seed_hash)
    return [round((raw[index] / 255.0) * 2.0 - 1.0, 8) for index in range(dimensions)]
