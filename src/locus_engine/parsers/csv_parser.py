"""CSV / TSV parser (Stage 3.2).

A dependency-free parser that turns delimited text into an IR table, preserving
row/column structure and attaching a ``SourceLocation`` (with character offsets) to
the table. Used as the working parser for the deterministic vertical slice; heavier
document parsers (Docling, OCR) are optional plugins with the same interface.

Requirements: 3.1, 3.2, 3.3, 3.4.
"""

from __future__ import annotations

import csv
import io

from locus_engine.errors import ParserError
from locus_engine.ir import (
    IntermediateRepresentation,
    IRElement,
    IRElementKind,
    IRTable,
)
from locus_engine.plugins import RawSource
from locus_engine.provenance import CharSpan, SourceLocation


class CsvParser:
    """Parses CSV and TSV content into an IR table."""

    name = "csv"
    content_types: tuple[str, ...] = ("text/csv", "text/tab-separated-values")

    def supports(self, content_type: str) -> bool:
        return content_type in self.content_types

    def parse(self, raw: RawSource) -> IntermediateRepresentation:
        if raw.data is None:
            raise ParserError(raw.source_id, "csv parser requires raw bytes")
        try:
            text = raw.data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ParserError(raw.source_id, f"decode failed: {exc}") from exc

        delimiter = "\t" if raw.content_type == "text/tab-separated-values" else ","
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        rows = [row for row in reader if row]
        if not rows:
            raise ParserError(raw.source_id, "no rows found")

        location = SourceLocation(
            source_id=raw.source_id,
            index=0,
            char_span=CharSpan(start=0, end=len(text)),
            note="csv table",
        )
        table = IRTable(cells=rows, location=location)
        element = IRElement(kind=IRElementKind.TABLE, table=table, location=location)
        return IntermediateRepresentation(
            source_id=raw.source_id,
            content_type=raw.content_type,
            elements=[element],
        )
