from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row


class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def connect(self, *, autocommit: bool = False) -> Connection:
        return psycopg.connect(
            self.database_url,
            autocommit=autocommit,
            row_factory=dict_row,
            connect_timeout=10,
            application_name="soaiacore-p0-runtime",
        )

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        with self.connect() as connection:
            with connection.transaction():
                yield connection

    def ping(self) -> bool:
        with self.connect(autocommit=True) as connection:
            row = connection.execute("SELECT 1 AS healthy").fetchone()
            return bool(row and row["healthy"] == 1)

