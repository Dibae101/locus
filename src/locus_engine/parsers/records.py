"""Structured records parser (Stage 9.2).

Maps already-structured records (from API or DB connectors) into an IR table,
preserving each record as a row and attaching a record-index ``SourceLocation``.

Requirements: 3.1, 3.2, 3.3.
"""

from __future__ import annotations

from locus_engine.errors import ParserError
from locus_engine.ir import (
    IntermediateRepresentation,
    IRElement,
    IRElementKind,
    IRTable,
)
from locus_engine.plugins import RawSource
from locus_engine.provenance import SourceLocation


class RecordsParser:
    """Parses structured records into an IR table."""

    name = "records"
    content_types = ("application/json", "application/x-records")

    def supports(self, content_type: str) -> bool:
        return content_type in self.content_types

    def parse(self, raw: RawSource) -> IntermediateRepresentation:
        if raw.records is None:
            raise ParserError(raw.source_id, "records parser requires structured records")
        if not raw.records:
            raise ParserError(raw.source_id, "no records found")

        # Union of keys across records, preserving first-seen order.
        columns: list[str] = []
        for rec in raw.records:
            for key in rec:
                if key not in columns:
                    columns.append(key)

        header = list(columns)
        grid: list[list[str]] = [header]
        for rec in raw.records:
            grid.append(["" if rec.get(c) is None else str(rec.get(c)) for c in columns])

        table_loc = SourceLocation(source_id=raw.source_id, index=0, note="records table")
        table = IRTable(cells=grid, location=table_loc)
        elements = [IRElement(kind=IRElementKind.TABLE, table=table, location=table_loc)]
        return IntermediateRepresentation(
            source_id=raw.source_id, content_type=raw.content_type, elements=elements
        )
