"""SQL emitter (Stage 9.4).

Writes the table (schema columns + a JSON lineage column) to a SQL table using the
standard library ``sqlite3`` by default; a connection factory can be injected for
other DB-API backends. Empty results still create the table with columns (Req 8.2);
an inaccessible destination records an ``EmitError`` (Req 8.7).

Requirements: 8.1, 8.2, 8.3, 8.5, 8.7.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from typing import Any

from locus_engine.emit.common import LINEAGE_COLUMN, cell_provenance_dict
from locus_engine.errors import EmitError
from locus_engine.plugins import EmitResult
from locus_engine.table import ProvenancedTable

ConnectionFactory = Callable[[str], Any]


def _sqlite_factory(dsn: str) -> sqlite3.Connection:
    return sqlite3.connect(dsn)


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class SqlEmitter:
    """Emits rows to a SQL table named ``locus_output``."""

    name = "sql"
    fmt = "sql"

    def __init__(
        self,
        table_name: str = "locus_output",
        *,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        self._table = table_name
        self._factory = connection_factory or _sqlite_factory

    def emit(self, table: ProvenancedTable, dest: str) -> EmitResult:
        columns = [*table.columns, LINEAGE_COLUMN]
        try:
            conn = self._factory(dest)
        except Exception as exc:
            raise EmitError(dest, f"connection failed: {exc}") from exc
        try:
            self._create_table(conn, columns)
            lineage = cell_provenance_dict(table)
            written = 0
            for i, row in enumerate(table.rows):
                values = [
                    row.cells[c].value if c in row.cells else None for c in table.columns
                ]
                values.append(json.dumps(lineage[i]))
                placeholders = ", ".join("?" for _ in columns)
                col_list = ", ".join(_quote_ident(c) for c in columns)
                conn.execute(
                    f"INSERT INTO {_quote_ident(self._table)} ({col_list}) "  # noqa: S608
                    f"VALUES ({placeholders})",
                    values,
                )
                written += 1
            conn.commit()
        except EmitError:
            raise
        except Exception as exc:
            raise EmitError(dest, str(exc)) from exc
        finally:
            conn.close()
        return EmitResult(destination=dest, rows_written=written)

    def _create_table(self, conn: Any, columns: list[str]) -> None:
        col_defs = ", ".join(f"{_quote_ident(c)} TEXT" for c in columns)
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {_quote_ident(self._table)} ({col_defs})"  # noqa: S608
        )
