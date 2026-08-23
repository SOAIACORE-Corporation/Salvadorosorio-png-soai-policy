from __future__ import annotations

from collections.abc import Callable
from typing import Any

from psycopg import Connection
from psycopg.types.json import Jsonb

from .errors import contract_error
from .hashing import sha256_json, sha256_text


def execute_idempotent(
    connection: Connection,
    *,
    operation: str,
    key: str,
    request_payload: dict[str, Any],
    resource_type: str,
    action: Callable[[], tuple[str, dict[str, Any]]],
) -> tuple[dict[str, Any], bool]:
    normalized_key = key.strip()
    if not normalized_key or len(normalized_key) > 200:
        raise contract_error(
            "IDEMPOTENCY_KEY_INVALID",
            "Idempotency-Key must contain 1 to 200 characters",
            "CORE_API",
            status_code=400,
        )

    key_hash = sha256_text(normalized_key)
    request_hash = sha256_json(request_payload)
    connection.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (f"{operation}:{key_hash}",),
    )
    existing = connection.execute(
        """
        SELECT request_hash,response_payload
        FROM soa_ops.idempotency_keys
        WHERE operation=%s AND key_hash=%s
        """,
        (operation, key_hash),
    ).fetchone()
    if existing:
        if existing["request_hash"] != request_hash:
            raise contract_error(
                "IDEMPOTENCY_CONFLICT",
                "Idempotency-Key was already used with a different request",
                "CORE_API",
                status_code=409,
            )
        return dict(existing["response_payload"]), True

    resource_id, response = action()
    connection.execute(
        """
        INSERT INTO soa_ops.idempotency_keys(
          operation,key_hash,request_hash,resource_type,resource_id,response_payload
        ) VALUES (%s,%s,%s,%s,%s,%s)
        """,
        (
            operation,
            key_hash,
            request_hash,
            resource_type,
            resource_id,
            Jsonb(response),
        ),
    )
    return response, False

