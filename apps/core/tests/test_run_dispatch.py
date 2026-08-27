from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

import soaiacore_core.main as core_main
from soaiacore_core.dispatcher import DISPATCHED, DispatchResult
from soaiacore_runtime.config import RuntimeSettings


class FakeDatabase:
    def __init__(self):
        self.committed = False

    @contextmanager
    def transaction(self):
        yield object()
        self.committed = True


def test_run_dispatch_happens_after_database_commit(monkeypatch):
    database = FakeDatabase()
    calls = []

    class Dispatcher:
        provider = "TEST"

        def dispatch(self, *, run_id, job_id):
            assert database.committed is True
            calls.append((run_id, job_id))
            return DispatchResult(status=DISPATCHED, provider=self.provider)

    def fake_idempotent(*_args, **_kwargs):
        return {
            "run_id": "run_test",
            "job_id": "job_test",
            "status": "QUEUED",
            "mode": "MOCK",
        }, False

    monkeypatch.setattr(core_main, "Database", lambda _url: database)
    monkeypatch.setattr(core_main, "execute_idempotent", fake_idempotent)
    settings = RuntimeSettings(
        database_url="postgresql://unused/soaiacore",
        provider_mode="MOCK",
        repo_root=Path("."),
        schema_dir=Path("schemas"),
        migration_dir=Path("db/migrations"),
        fixture_dir=Path("fixtures"),
        storage_account_name=None,
        storage_container_name=None,
    )
    app = core_main.create_app(settings)
    app.state.job_dispatcher = Dispatcher()

    with TestClient(app) as client:
        response = client.post(
            "/v1/runs",
            json={
                "context_capsule_id": "capsule_test",
                "analysis_profile_id": "AP-101",
                "analysis_profile_version": "1.0.0",
                "purpose": "P1_DISPATCH_TEST",
                "mode": "MOCK",
                "mock_fixture_id": "fixture",
            },
            headers={"Idempotency-Key": "dispatch-test"},
        )

    assert response.status_code == 202
    assert calls == [("run_test", "job_test")]
    assert response.headers["X-Dispatch-Status"] == DISPATCHED
    assert response.json()["dispatch_status"] == DISPATCHED
    assert response.json()["dispatch_retryable"] is False
