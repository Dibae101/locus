"""Parquet emitter (Stage 3.5).

Writes the table (schema columns + lineage column) to a Parquet file. The lineage
column is serialized as JSON text so it round-trips through Parquet. An inaccessible
destination records an ``EmitError`` (Req 8.7).

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7.
"""

from __future__ import annotations

import json

import pandas as pd

from locus_engine.emit.common import LINEAGE_COLUMN, records_with_lineage
from locus_engine.errors import EmitError
from locus_engine.plugins import EmitResult
from locus_engine.table import ProvenancedTable


class ParquetEmitter:
    """Emits a Parquet file at ``dest``."""

    name = "parquet"
    fmt = "parquet"

    def emit(self, table: ProvenancedTable, dest: str) -> EmitResult:
        columns = [*table.columns, LINEAGE_COLUMN]
        if not table.rows:
            frame = pd.DataFrame(columns=columns)
        else:
            records = records_with_lineage(table)
            for rec in records:
                rec[LINEAGE_COLUMN] = json.dumps(rec[LINEAGE_COLUMN])
            frame = pd.DataFrame(records, columns=columns)

        try:
            frame.to_parquet(dest, index=False)
        except (OSError, ValueError, ImportError) as exc:
            raise EmitError(dest, str(exc)) from exc
        return EmitResult(destination=dest, rows_written=len(frame))
