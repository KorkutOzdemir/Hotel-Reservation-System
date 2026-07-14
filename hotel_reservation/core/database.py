"""SQLite connection, query building and transaction helpers."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from hotel_reservation.config import AppSettings


class DatabaseManager:
    """Singleton wrapper around the SQLite connection."""

    _instance: "DatabaseManager | None" = None

    def __new__(cls, db_path: str | Path | None = None) -> "DatabaseManager":
        # One shared manager keeps every DAO on the same SQLite connection.
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str | Path | None = None) -> None:
        requested_path = Path(db_path or AppSettings.DB_PATH).resolve()
        if self._initialized:
            # Reusing the singleton is fine as long as the database path matches.
            if requested_path != self.db_path:
                if self._connection is not None:
                    raise ValueError(
                        f"DatabaseManager is already connected to {self.db_path}; "
                        f"close it before using {requested_path}."
                    )
                self.db_path = requested_path
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
            return
        self.db_path = requested_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: sqlite3.Connection | None = None
        self._transaction_depth = 0
        self._initialized = True

    def connect(self) -> sqlite3.Connection:
        # Open lazily so imports do not touch the database until it is needed.
        if self._connection is None:
            self._connection = sqlite3.connect(str(self.db_path))
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
        return self._connection

    def execute(
        self,
        sql: str,
        params: Iterable[Any] | None = None,
        *,
        commit: bool = True,
    ) -> sqlite3.Cursor:
        cursor = self.connect().execute(sql, tuple(params or ()))
        # Standalone writes commit immediately; transactions commit as a group.
        if commit and self._transaction_depth == 0:
            self.connect().commit()
        return cursor

    def executemany(
        self,
        sql: str,
        rows: Iterable[Iterable[Any]],
        *,
        commit: bool = True,
    ) -> sqlite3.Cursor:
        cursor = self.connect().executemany(sql, rows)
        # Bulk inserts use the same transaction-aware commit behavior.
        if commit and self._transaction_depth == 0:
            self.connect().commit()
        return cursor

    def query(self, sql: str, params: Iterable[Any] | None = None) -> list[sqlite3.Row]:
        # Return rows as sqlite3.Row so callers can access values by name.
        return list(self.connect().execute(sql, tuple(params or ())).fetchall())

    def query_one(self, sql: str, params: Iterable[Any] | None = None) -> sqlite3.Row | None:
        # Use this for lookups where zero or one row is expected.
        return self.connect().execute(sql, tuple(params or ())).fetchone()

    @contextmanager
    def transaction(self):
        # Nested service calls can share one outer transaction safely.
        connection = self.connect()
        self._transaction_depth += 1
        try:
            yield connection
        except Exception:
            self._transaction_depth = 0
            connection.rollback()
            raise
        else:
            self._transaction_depth -= 1
            if self._transaction_depth == 0:
                try:
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
        finally:
            if self._transaction_depth < 0:
                self._transaction_depth = 0

    def close(self) -> None:
        # Closing resets only the connection, not the singleton object.
        if self._connection is not None:
            self._connection.close()
            self._connection = None
