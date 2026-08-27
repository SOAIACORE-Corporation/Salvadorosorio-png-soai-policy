from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import quote_plus


def find_repo_root(start: Path | None = None) -> Path:
    explicit = os.getenv("SOAIACORE_ROOT")
    if explicit:
        root = Path(explicit).resolve()
        if (root / "schemas").is_dir() and (root / "db" / "migrations").is_dir():
            return root
        raise RuntimeError("SOAIACORE_ROOT does not contain schemas and db/migrations")

    candidates = [start or Path.cwd(), Path(__file__).resolve()]
    for candidate in candidates:
        for parent in [candidate, *candidate.parents]:
            if (parent / "schemas").is_dir() and (parent / "db" / "migrations").is_dir():
                return parent
    raise RuntimeError("SOAIACORE repository root could not be located")


def database_url_from_env() -> str:
    direct = os.getenv("DATABASE_URL")
    if direct:
        return direct

    host = os.getenv("POSTGRES_HOST", "127.0.0.1")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "soaiacore")
    user = quote_plus(os.getenv("POSTGRES_USER", "soaiacore"))
    password = quote_plus(os.getenv("POSTGRES_PASSWORD", ""))
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


@dataclass(frozen=True)
class RuntimeSettings:
    database_url: str
    provider_mode: str
    repo_root: Path
    schema_dir: Path
    migration_dir: Path
    fixture_dir: Path
    storage_account_name: str | None
    storage_container_name: str | None
    dispatch_mode: str = "LOCAL"
    azure_subscription_id: str | None = None
    azure_resource_group: str | None = None
    azure_container_app_job_name: str | None = None
    azure_management_api_version: str = "2024-03-01"
    dispatch_timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "RuntimeSettings":
        root = find_repo_root()
        return cls(
            database_url=database_url_from_env(),
            provider_mode=os.getenv("SOAIACORE_PROVIDER_MODE", "MOCK").upper(),
            repo_root=root,
            schema_dir=Path(os.getenv("SOAIACORE_SCHEMA_DIR", root / "schemas")),
            migration_dir=Path(
                os.getenv("SOAIACORE_MIGRATION_DIR", root / "db" / "migrations")
            ),
            fixture_dir=Path(
                os.getenv(
                    "SOAIACORE_FIXTURE_DIR", root / "packages" / "mock-fixtures" / "v1"
                )
            ),
            storage_account_name=os.getenv("AZURE_STORAGE_ACCOUNT_NAME"),
            storage_container_name=os.getenv("AZURE_STORAGE_CONTAINER_NAME"),
            dispatch_mode=os.getenv("SOAIACORE_DISPATCH_MODE", "LOCAL").upper(),
            azure_subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID"),
            azure_resource_group=os.getenv("AZURE_RESOURCE_GROUP"),
            azure_container_app_job_name=os.getenv("AZURE_CONTAINER_APP_JOB_NAME"),
            azure_management_api_version=os.getenv(
                "AZURE_MANAGEMENT_API_VERSION", "2024-03-01"
            ),
            dispatch_timeout_seconds=float(
                os.getenv("SOAIACORE_DISPATCH_TIMEOUT_SECONDS", "10")
            ),
        )

