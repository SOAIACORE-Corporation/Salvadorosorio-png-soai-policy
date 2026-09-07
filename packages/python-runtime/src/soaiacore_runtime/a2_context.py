from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .a2_persistence import canonical_memory_as_of
from .database import Database


@dataclass(frozen=True)
class A2CanonicalMemoryReader:
    """Bind the provider-neutral ContextBuilder reader contract to A2 persistence.

    The adapter is read-only: it delegates exclusively to the existing bitemporal
    ``canonical_memory_as_of`` query and introduces no migration, write path, or
    live-environment behavior.
    """

    database: Database

    def __call__(
        self,
        *,
        project_scope: str,
        valid_at: datetime,
        recorded_at: datetime,
    ) -> list[dict[str, Any]]:
        return canonical_memory_as_of(
            self.database,
            project_scope=project_scope,
            valid_at=valid_at,
            recorded_at=recorded_at,
        )
