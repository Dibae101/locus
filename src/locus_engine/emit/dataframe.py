"""DataFrame emitter (Stage 3.5).

Builds a pandas DataFrame with the schema columns plus a reserved lineage column.
Empty results still produce a DataFrame with the schema columns and zero rows
(Req 8.2). Engine provenance is recorded on the returned frame's ``attrs``.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6.
"""

from __future__ import annotations

import pandas as pd

from locus_engine.emit.common import LINEAGE_COLUMN, records_with_lineage
from locus_engine.plugins import EmitResult
from locus_engine.table import ProvenancedTable


class DataFrameEmitter:
    """Emits an in-memory pandas DataFrame."""

    name = "dataframe"
    fmt = "dataframe"

    def to_frame(self, table: ProvenancedTable) -> pd.DataFrame:
        columns = [*table.columns, LINEAGE_COLUMN]
        if not table.rows:
            frame = pd.DataFrame(columns=columns)  # Req 8.2
        else:
            frame = pd.DataFrame(records_with_lineage(table), columns=columns)
        frame.attrs["produced_by_engine"] = table.produced_by_engine  # Req 8.6
        frame.attrs["grounding_mode"] = table.grounding_mode
        return frame

    def emit(self, table: ProvenancedTable, dest: str) -> EmitResult:
        frame = self.to_frame(table)
        # For the in-memory emitter, "dest" is a logical label; the frame is the output.
        self.last_frame = frame
        return EmitResult(destination=dest or "<dataframe>", rows_written=len(frame))
