from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from azure.identity import DefaultAzureCredential

from soaiacore_runtime.config import RuntimeSettings


DISPATCHED = "DISPATCHED"
QUEUED_DISPATCH_PENDING = "QUEUED_DISPATCH_PENDING"


@dataclass(frozen=True)
class DispatchResult:
    status: str
    provider: str
    retryable: bool = False
    error_code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "dispatch_status": self.status,
            "dispatch_provider": self.provider,
            "dispatch_retryable": self.retryable,
        }
        if self.error_code:
            result["dispatch_error_code"] = self.error_code
        return result

    @classmethod
    def pending(
        cls, provider: str, *, error_code: str = "DISPATCH_UNAVAILABLE"
    ) -> "DispatchResult":
        return cls(
            status=QUEUED_DISPATCH_PENDING,
            provider=provider,
            retryable=True,
            error_code=error_code,
        )


class JobDispatcher(Protocol):
    provider: str

    def dispatch(self, *, run_id: str, job_id: str) -> DispatchResult:
        """Wake the worker after the Run+Job transaction has committed."""


class LocalJobDispatcher:
    """No-cloud dispatcher used by local runs and acceptance tests.

    A callback can be supplied by a test harness or an explicit local hook. The
    Core process never executes the lifecycle itself; the real Worker remains
    responsible for claiming and running the queued job.
    """

    provider = "LOCAL_MANUAL"

    def __init__(self, trigger: Callable[[str, str], None] | None = None):
        self._trigger = trigger

    def dispatch(self, *, run_id: str, job_id: str) -> DispatchResult:
        if self._trigger is None:
            return DispatchResult.pending(
                self.provider, error_code="LOCAL_MANUAL_TRIGGER_REQUIRED"
            )
        try:
            self._trigger(run_id, job_id)
        except Exception:
            return DispatchResult.pending(self.provider, error_code="LOCAL_DISPATCH_FAILED")
        return DispatchResult(status=DISPATCHED, provider=self.provider)


class UnavailableJobDispatcher:
    """Safe startup fallback when cloud dispatch is selected but misconfigured."""

    def __init__(self, provider: str, error_code: str):
        self.provider = provider
        self.error_code = error_code

    def dispatch(self, *, run_id: str, job_id: str) -> DispatchResult:
        del run_id, job_id
        return DispatchResult.pending(self.provider, error_code=self.error_code)


class AzureContainerAppJobDispatcher:
    provider = "AZURE_CONTAINER_APPS_JOB"
    _scope = "https://management.azure.com/.default"

    def __init__(self, settings: RuntimeSettings):
        missing = [
            name
            for name, value in (
                ("AZURE_SUBSCRIPTION_ID", settings.azure_subscription_id),
                ("AZURE_RESOURCE_GROUP", settings.azure_resource_group),
                ("AZURE_CONTAINER_APP_JOB_NAME", settings.azure_container_app_job_name),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Azure dispatcher configuration missing: {','.join(missing)}"
            )
        self._subscription_id = settings.azure_subscription_id  # type: ignore[assignment]
        self._resource_group = settings.azure_resource_group  # type: ignore[assignment]
        self._job_name = settings.azure_container_app_job_name  # type: ignore[assignment]
        self._api_version = settings.azure_management_api_version
        self._timeout = settings.dispatch_timeout_seconds
        self._credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        self._locks: defaultdict[str, Lock] = defaultdict(Lock)
        self._successful_jobs: set[str] = set()

    def dispatch(self, *, run_id: str, job_id: str) -> DispatchResult:
        # Concurrent duplicate wake-ups are collapsed in-process. If another
        # process also wakes the job, PostgreSQL claim locking still guarantees
        # at-most-one lifecycle execution.
        with self._locks[job_id]:
            if job_id in self._successful_jobs:
                return DispatchResult(status=DISPATCHED, provider=self.provider)
            result = self._dispatch_once(run_id=run_id, job_id=job_id)
            if result.status == DISPATCHED:
                self._successful_jobs.add(job_id)
            return result

    def _dispatch_once(self, *, run_id: str, job_id: str) -> DispatchResult:
        del run_id  # The Worker discovers the queued job from canonical PostgreSQL state.
        try:
            token = self._credential.get_token(self._scope).token
            path = "/subscriptions/{}/resourceGroups/{}/providers/Microsoft.App/jobs/{}/start".format(
                quote(self._subscription_id, safe=""),
                quote(self._resource_group, safe=""),
                quote(self._job_name, safe=""),
            )
            request = Request(
                "https://management.azure.com"
                f"{path}?api-version={quote(self._api_version, safe='')}",
                method="POST",
                data=b"",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}",
                    "Content-Length": "0",
                },
            )
            with urlopen(request, timeout=self._timeout) as response:
                if 200 <= response.status < 300:
                    return DispatchResult(status=DISPATCHED, provider=self.provider)
                return DispatchResult.pending(
                    self.provider, error_code=f"AZURE_DISPATCH_HTTP_{response.status}"
                )
        except HTTPError as error:
            retryable = error.code == 429 or error.code >= 500
            return DispatchResult(
                status=QUEUED_DISPATCH_PENDING,
                provider=self.provider,
                retryable=retryable,
                error_code=f"AZURE_DISPATCH_HTTP_{error.code}",
            )
        except (URLError, TimeoutError, OSError):
            return DispatchResult.pending(self.provider, error_code="AZURE_DISPATCH_UNAVAILABLE")
        except Exception:
            # Do not expose token, URL, or SDK details in the API response.
            return DispatchResult.pending(self.provider, error_code="AZURE_DISPATCH_FAILED")


def build_dispatcher(settings: RuntimeSettings) -> JobDispatcher:
    if settings.dispatch_mode.upper() == "AZURE":
        try:
            return AzureContainerAppJobDispatcher(settings)
        except RuntimeError:
            return UnavailableJobDispatcher(
                AzureContainerAppJobDispatcher.provider,
                "AZURE_DISPATCHER_MISCONFIGURED",
            )
    return LocalJobDispatcher()
