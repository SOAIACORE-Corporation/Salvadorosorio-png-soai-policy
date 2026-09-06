from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys

from soaiacore_runtime.a2_persistence import apply_a2_persistence, verify_a2_persistence
from soaiacore_runtime.config import RuntimeSettings
from soaiacore_runtime.database import Database
from soaiacore_runtime.errors import RuntimeContractError
from soaiacore_runtime.lifecycle import run_one
from soaiacore_runtime.migrations import apply_migrations, verify_migrations


def _emit(event: str, **fields) -> None:
    print(json.dumps({"event": event, **fields}, sort_keys=True, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="soaiacore-worker")
    parser.add_argument(
        "command",
        choices=("migrate", "precheck", "run-one", "a2-migrate", "a2-verify"),
    )
    args = parser.parse_args(argv)
    settings = RuntimeSettings.from_env()
    database = Database(settings.database_url)
    a2_migration_dir = settings.repo_root / "db" / "a2_migrations"

    try:
        if args.command == "migrate":
            applied = apply_migrations(database, settings.migration_dir)
            _emit("MIGRATE_PASS", applied=applied, count=len(applied))
            return 0
        if args.command == "a2-migrate":
            applied = apply_a2_persistence(
                database,
                base_migration_dir=settings.migration_dir,
                a2_migration_dir=a2_migration_dir,
            )
            _emit(
                "A2_MIGRATE_PASS",
                base=applied["base"],
                base_count=len(applied["base"]),
                overlay=applied["a2_overlay"],
                overlay_count=len(applied["a2_overlay"]),
            )
            return 0
        if args.command == "a2-verify":
            verification = verify_a2_persistence(
                database,
                base_migration_dir=settings.migration_dir,
                a2_migration_dir=a2_migration_dir,
            )
            _emit(
                "A2_VERIFY_PASS",
                vector_installed=verification.vector_installed,
                base_migrations=len(verification.base_migrations),
                overlay_migrations=len(verification.overlay_migrations),
                relations=len(verification.relations),
                functions=len(verification.functions),
            )
            return 0
        if args.command == "precheck":
            if settings.provider_mode != "MOCK":
                _emit("PRECHECK_BLOCKED", blocker="LIVE_PROVIDER_FORBIDDEN")
                return 20
            checksums = verify_migrations(database, settings.migration_dir)
            _emit("PRECHECK_PASS", migrations=len(checksums), provider_mode="MOCK")
            return 0
        result = run_one(database, settings)
        _emit("RUN_ONE_RESULT", **asdict(result))
        return result.exit_code
    except RuntimeContractError as error:
        _emit("WORKER_BLOCKED", code=error.code, stage=error.stage, retryable=error.retryable)
        gated_commands = {"migrate", "precheck", "a2-migrate", "a2-verify"}
        return 21 if args.command in gated_commands else 23
    except Exception:
        _emit("WORKER_BLOCKED", code="INTERNAL_ERROR", stage=args.command.upper(), retryable=False)
        gated_commands = {"migrate", "precheck", "a2-migrate", "a2-verify"}
        return 21 if args.command in gated_commands else 23


if __name__ == "__main__":
    sys.exit(main())
