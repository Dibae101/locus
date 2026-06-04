"""Tests for the Intermediate Representation (Stage 1.4)."""

from __future__ import annotations

from locus_engine.ir import (
    IR_SCHEMA_VERSION,
    IntermediateRepresentation,
    IRElement,
    IRElementKind,
    IRTable,
)
from locus_engine.provenance import SourceLocation


def _loc(idx: int = 0) -> SourceLocation:
    return SourceLocation(source_id="doc-1", index=idx)


def test_ir_schema_version() -> None:
    ir = IntermediateRepresentation(source_id="doc-1", content_type="application/pdf")
    assert ir.schema_version == IR_SCHEMA_VERSION == "ir/v1"


def test_table_preserved_as_rows_and_cols() -> None:
    table = IRTable(cells=[["h1", "h2"], ["a", "b"]], location=_loc(1))
    el = IRElement(kind=IRElementKind.TABLE, table=table, location=_loc(1))
    ir = IntermediateRepresentation(
        source_id="doc-1", content_type="application/pdf", elements=[el]
    )
    tables = ir.tables()
    assert len(tables) == 1
    assert tables[0].table is not None
    assert tables[0].table.cells == [["h1", "h2"], ["a", "b"]]


def test_every_element_is_located() -> None:
    ir = IntermediateRepresentation(
        source_id="doc-1",
        content_type="text/html",
        elements=[
            IRElement(kind=IRElementKind.HEADING, text="Title", location=_loc(0)),
            IRElement(kind=IRElementKind.PARAGRAPH, text="Body", location=_loc(0)),
        ],
    )
    for el in ir.elements:
        assert el.location.source_id == "doc-1"
