"""SQL database connector (Stage 9.1).

Reads the result set of a SQL query as structured records. Uses the standard library
``sqlite3`` by default (no heavy deps); a DB-API connection factory can be injected
for other databases. Credentials/DSN arrive via config (Req 1.6).

Requirements: 1.1, 1.2, 1.3, 1.6.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any

from locus_engine.errors import ConnectorError
from locus_engine.plugins import RawSource, SourceRef

# A connection factory returns a DB-API connection for a given DSN.
ConnectionFactory = Callable[[str], Any]


def _sqlite_factory(dsn: str) -> sqlite3.Connection:
    conn = sqlite3.connect(dsn)
    conn.row_factory = sqlite3.Row
    return conn


class SqlConnector:
    """Reads a SQL query result set as records.

    ``SourceRef.uri`` is the DSN; the query is supplied at construction time.
    """

    name = "sql"

    def __init__(
        self,
        query: str,
        *,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        self._query = query
        self._factory = connection_factory or _sqlite_factory

    def supports(self, ref: SourceRef) -> bool:
        return ref.kind in ("sql", "db")

    def read(self, ref: SourceRef) -> RawSource:
        try:
            conn = self._factory(ref.uri)
        except Exception as exc:  # pragma: no cover - driver/DSN issues
            raise ConnectorError(ref.uri, f"connection failed: {exc}") from exc
        try:
            cursor = conn.execute(self._query)
            rows = cursor.fetchall()
            records = [self._row_to_dict(r) for r in rows]
        except Exception as exc:
            raise ConnectorError(ref.uri, f"query failed: {exc}") from exc
        finally:
            conn.close()
        return RawSource(
            source_id=f"{ref.uri}#query", content_type="application/x-records", records=records
        )

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        if isinstance(row, sqlite3.Row):
            keys = row.keys()
            return {k: row[k] for k in keys}
        if isinstance(row, dict):
            return row
        # tuple fallback: name columns positionally
        return {f"col_{i}": v for i, v in enumerate(row)}
