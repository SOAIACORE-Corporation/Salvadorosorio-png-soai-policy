from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError

import soaiacore_core.dispatcher as dispatcher_module
from soaiacore_core.dispatcher import (
    AzureContainerAppJobDispatcher,
    DISPATCHED,
    LocalJobDispatcher,
    QUEUED_DISPATCH_PENDING,
)
from soaiacore_runtime.config import RuntimeSettings


def settings(**overrides) -> RuntimeSettings:
    values = {
        "database_url": "postgresql://localhost/soaiacore",
        "provider_mode": "MOCK",
        "repo_root": Path("."),
        "schema_dir": Path("schemas"),
        "migration_dir": Path("db/migrations"),
        "fixture_dir": Path("fixtures"),
        "storage_account_name": None,
        "storage_container_name": None,
        "dispatch_mode": "AZURE",
        "azure_subscription_id": "sub-123",
        "azure_resource_group": "rg-pilot",
        "azure_container_app_job_name": "caj-worker-abc",
    }
    values.update(overrides)
    return RuntimeSettings(**values)


def test_local_dispatcher_requires_explicit_manual_hook():
    result = LocalJobDispatcher().dispatch(run_id="run-1", job_id="job-1")

    assert result.status == QUEUED_DISPATCH_PENDING
    assert result.provider == "LOCAL_MANUAL"
    assert result.error_code == "LOCAL_MANUAL_TRIGGER_REQUIRED"
    assert result.retryable is True


def test_local_dispatcher_calls_hook_without_running_lifecycle():
    calls = []
    result = LocalJobDispatcher(lambda run_id, job_id: calls.append((run_id, job_id))).dispatch(
        run_id="run-1", job_id="job-1"
    )

    assert result.status == DISPATCHED
    assert calls == [("run-1", "job-1")]


def test_azure_dispatcher_starts_existing_job_without_secret_leak(monkeypatch):
    captured = {}

    class Credential:
        def get_token(self, scope):
            captured["scope"] = scope
            return type("Token", (), {"token": "opaque-token"})()

    class Response:
        status = 202

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(dispatcher_module, "DefaultAzureCredential", lambda **_: Credential())
    monkeypatch.setattr(dispatcher_module, "urlopen", fake_urlopen)

    result = AzureContainerAppJobDispatcher(settings()).dispatch(run_id="run-1", job_id="job-1")
    request = captured["request"]

    assert result.status == DISPATCHED
    assert captured["scope"] == "https://management.azure.com/.default"
    assert request.full_url == (
        "https://management.azure.com/subscriptions/sub-123/resourceGroups/rg-pilot/"
        "providers/Microsoft.App/jobs/caj-worker-abc/start?api-version=2024-03-01"
    )
    assert request.get_header("Authorization") == "Bearer opaque-token"
    assert "run-1" not in request.full_url
    assert captured["timeout"] == 10.0


def test_azure_dispatcher_deduplicates_successful_wakeups(monkeypatch):
    calls = []

    class Credential:
        def get_token(self, _scope):
            return type("Token", (), {"token": "opaque-token"})()

    class Response:
        status = 202

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def fake_urlopen(_request, timeout):
        calls.append(True)
        return Response()

    monkeypatch.setattr(dispatcher_module, "DefaultAzureCredential", lambda **_: Credential())
    monkeypatch.setattr(dispatcher_module, "urlopen", fake_urlopen)
    dispatcher = AzureContainerAppJobDispatcher(settings())

    first = dispatcher.dispatch(run_id="run-1", job_id="job-1")
    second = dispatcher.dispatch(run_id="run-1", job_id="job-1")

    assert first.status == second.status == DISPATCHED
    assert len(calls) == 1


def test_azure_dispatcher_keeps_job_queued_when_management_api_is_unavailable(monkeypatch):
    class Credential:
        def get_token(self, _scope):
            return type("Token", (), {"token": "opaque-token"})()

    monkeypatch.setattr(dispatcher_module, "DefaultAzureCredential", lambda **_: Credential())

    def unavailable(*_args, **_kwargs):
        raise HTTPError("https://management.azure.com", 503, "unavailable", {}, None)

    monkeypatch.setattr(dispatcher_module, "urlopen", unavailable)

    result = AzureContainerAppJobDispatcher(settings()).dispatch(run_id="run-1", job_id="job-1")

    assert result.status == QUEUED_DISPATCH_PENDING
    assert result.error_code == "AZURE_DISPATCH_HTTP_503"
    assert result.retryable is True
