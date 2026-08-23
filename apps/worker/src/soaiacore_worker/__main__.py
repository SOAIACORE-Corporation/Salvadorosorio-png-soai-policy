from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys

from soaiacore_runtime.config import RuntimeSettings
from soaiacore_runtime.database import Database
from soaiacore_runtime.errors import RuntimeContractError
from soaiacore_runtime.lifecycle import run_one
from soaiacore_runtime.migrations import apply_migrations, verify_migrations


def _emit(event: str, **fields) -> None:
    print(json.dumps({"event": event, **fields}, sort_keys=True, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="soaiacore-worker")
    parser.add_argument("command", choices=("migrate", "precheck", "run-one"))
    args = parser.parse_args(argv)
    settings = RuntimeSettings.from_env()
    database = Database(settings.database_url)

    try:
        if args.command == "migrate":
            applied = apply_migrations(database, settings.migration_dir)
            _emit("MIGRATE_PASS", applied=applied, count=len(applied))
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
        return 21 if args.command in {"migrate", "precheck"} else 23
    except Exception:
        _emit("WORKER_BLOCKED", code="INTERNAL_ERROR", stage=args.command.upper(), retryable=False)
        return 21 if args.command in {"migrate", "precheck"} else 23


if __name__ == "__main__":
    sys.exit(main())
