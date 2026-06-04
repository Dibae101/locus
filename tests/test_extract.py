"""Tests for the deterministic extraction engine (Stage 3.3)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, field_validator

from locus_engine.errors import ExtractionError
from locus_engine.extract.deterministic import DeterministicEngine
from locus_engine.ir import (
    IntermediateRepresentation,
    IRElement,
    IRElementKind,
    IRTable,
)
from locus_engine.plugins import ExtractContext, ResolvedSchema
from locus_engine.provenance import OpKind, SourceLocation


def _ir(grid: list[list[str]]) -> IntermediateRepresentation:
    loc = SourceLocation(source_id="s1", index=0)
    el = IRElement(kind=IRElementKind.TABLE, table=IRTable(cells=grid, location=loc), location=loc)
    return IntermediateRepresentation(source_id="s1", content_type="text/csv", elements=[el])


def test_infer_mode_uses_header() -> None:
    ir = _ir([["name", "amount"], ["Acme", "100"], ["Globex", "200"]])
    schema = ResolvedSchema(mode="infer")
    table = DeterministicEngine().extract(ir, schema, ExtractContext(schema=schema))
    assert table.columns == ["name", "amount"]
    assert table.value_records() == [
        {"name": "Acme", "amount": "100"},
        {"name": "Globex", "amount": "200"},
    ]


def test_each_cell_has_extract_lineage_and_location() -> None:
    ir = _ir([["name"], ["Acme"]])
    schema = ResolvedSchema(mode="infer")
    table = DeterministicEngine().extract(ir, schema, ExtractContext(schema=schema))
    cell = table.rows[0].cells["name"]
    assert cell.provenance.locations[0].source_id == "s1"
    assert cell.provenance.lineage[0].op is OpKind.EXTRACT


def test_no_table_raises() -> None:
    ir = IntermediateRepresentation(source_id="s1", content_type="text/csv", elements=[])
    schema = ResolvedSchema(mode="infer")
    with pytest.raises(ExtractionError):
        DeterministicEngine().extract(ir, schema, ExtractContext(schema=schema))


class InvoiceModel(BaseModel):
    name: str
    amount: int

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce(cls, v: object) -> object:
        return v


def test_strict_mode_validation_failure_raises() -> None:
    ir = _ir([["name", "amount"], ["Acme", "not-a-number"]])
    schema = ResolvedSchema(mode="strict", columns=["name", "amount"], model=InvoiceModel)
    with pytest.raises(ExtractionError):
        DeterministicEngine().extract(ir, schema, ExtractContext(schema=schema, retry_limit=2))
