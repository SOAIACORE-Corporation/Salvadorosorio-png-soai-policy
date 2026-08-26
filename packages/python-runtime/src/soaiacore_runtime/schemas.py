from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .config import RuntimeSettings
from .errors import contract_error


@lru_cache(maxsize=32)
def _load_schema(path_text: str) -> dict[str, Any]:
    path = Path(path_text)
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def load_schema(name: str, settings: RuntimeSettings | None = None) -> dict[str, Any]:
    active = settings or RuntimeSettings.from_env()
    path = (active.schema_dir / name).resolve()
    if path.parent != active.schema_dir.resolve() or not path.is_file():
        raise contract_error(
            "SCHEMA_NOT_FOUND",
            f"Authoritative schema {name} was not found",
            "CONTRACT",
            status_code=500,
        )
    return _load_schema(str(path))


def validate_payload(
    schema_name: str,
    payload: dict[str, Any],
    *,
    stage: str = "CONTRACT",
    settings: RuntimeSettings | None = None,
) -> None:
    schema = load_schema(schema_name, settings)
    try:
        Draft202012Validator(schema).validate(payload)
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.absolute_path) or "$"
        raise contract_error(
            "SCHEMA_VALIDATION_FAILED",
            f"{schema_name} rejected payload at {path}: {exc.message}",
            stage,
            status_code=422,
            details={"schema": schema_name, "path": path},
        ) from exc

