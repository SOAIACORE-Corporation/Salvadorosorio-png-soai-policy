from __future__ import annotations

from pathlib import Path
import hashlib

from fastapi.testclient import TestClient
import pytest

from soaiacore_core.auth import OperatorAuthError, sign_operator_context, verify_operator_context
from soaiacore_core.main import create_app
from soaiacore_runtime.config import RuntimeSettings


SECRET = "test-only-internal-auth-secret-32-bytes-minimum"
OPERATOR_ID = "op_0123456789abcdef01234567"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def protected_settings() -> RuntimeSettings:
    return RuntimeSettings(
        database_url="postgresql://unused/soaiacore",
        provider_mode="MOCK",
        repo_root=Path("."),
        schema_dir=Path("schemas"),
        migration_dir=Path("db/migrations"),
        fixture_dir=Path("fixtures"),
        storage_account_name=None,
        storage_container_name=None,
        internal_auth_required=True,
        internal_auth_secret=SECRET,
    )


def signed_headers(*, role: str = "OPERATOR", now: int = 1_700_000_000) -> dict[str, str]:
    correlation_id = "corr_security_test"
    timestamp = str(now)
    signature = sign_operator_context(
        SECRET,
        method="GET",
        path="/v1/projects",
        timestamp=timestamp,
        correlation_id=correlation_id,
        operator_id=OPERATOR_ID,
        role=role,
        content_sha256=EMPTY_SHA256,
    )
    return {
        "X-Correlation-ID": correlation_id,
        "X-SOAIA-Operator-ID": OPERATOR_ID,
        "X-SOAIA-Operator-Role": role,
        "X-SOAIA-Auth-Timestamp": timestamp,
        "X-SOAIA-Auth-Signature": signature,
        "X-SOAIA-Content-SHA256": EMPTY_SHA256,
    }


def test_core_rejects_unauthenticated_product_request_without_secret_leak():
    with TestClient(create_app(protected_settings())) as client:
        response = client.get("/v1/projects")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "OPERATOR_AUTH_REQUIRED"
    assert SECRET not in response.text


def test_core_accepts_signed_operator_context_and_rejects_unknown_role():
    headers = signed_headers()
    context = verify_operator_context(
        SECRET,
        method="GET",
        path="/v1/projects",
        timestamp=headers["X-SOAIA-Auth-Timestamp"],
        correlation_id=headers["X-Correlation-ID"],
        operator_id=headers["X-SOAIA-Operator-ID"],
        role=headers["X-SOAIA-Operator-Role"],
        signature=headers["X-SOAIA-Auth-Signature"],
        content_sha256=headers["X-SOAIA-Content-SHA256"],
        actual_content_sha256=EMPTY_SHA256,
        now=1_700_000_000,
    )
    assert context.operator_id == OPERATOR_ID
    assert context.role == "OPERATOR"

    invalid = signed_headers(role="READER")
    with pytest.raises(OperatorAuthError, match="role is not allowed"):
        verify_operator_context(
            SECRET,
            method="GET",
            path="/v1/projects",
            timestamp=invalid["X-SOAIA-Auth-Timestamp"],
            correlation_id=invalid["X-Correlation-ID"],
            operator_id=invalid["X-SOAIA-Operator-ID"],
            role=invalid["X-SOAIA-Operator-Role"],
            signature=invalid["X-SOAIA-Auth-Signature"],
            content_sha256=invalid["X-SOAIA-Content-SHA256"],
            actual_content_sha256=EMPTY_SHA256,
            now=1_700_000_000,
        )


def test_core_rejects_expired_or_tampered_context():
    headers = signed_headers(now=1_700_000_000)
    with pytest.raises(OperatorAuthError) as expired:
        verify_operator_context(
            SECRET,
            method="GET",
            path="/v1/projects",
            timestamp=headers["X-SOAIA-Auth-Timestamp"],
            correlation_id=headers["X-Correlation-ID"],
            operator_id=headers["X-SOAIA-Operator-ID"],
            role=headers["X-SOAIA-Operator-Role"],
            signature=headers["X-SOAIA-Auth-Signature"],
            content_sha256=headers["X-SOAIA-Content-SHA256"],
            actual_content_sha256=EMPTY_SHA256,
            now=1_700_000_121,
        )
    assert expired.value.code == "OPERATOR_AUTH_EXPIRED"

    with pytest.raises(OperatorAuthError) as tampered:
        verify_operator_context(
            SECRET,
            method="GET",
            path="/v1/projects/other",
            timestamp=headers["X-SOAIA-Auth-Timestamp"],
            correlation_id=headers["X-Correlation-ID"],
            operator_id=headers["X-SOAIA-Operator-ID"],
            role=headers["X-SOAIA-Operator-Role"],
            signature=headers["X-SOAIA-Auth-Signature"],
            content_sha256=headers["X-SOAIA-Content-SHA256"],
            actual_content_sha256=EMPTY_SHA256,
            now=1_700_000_000,
        )
    assert tampered.value.code == "OPERATOR_AUTH_INVALID"
