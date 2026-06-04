"""Tests for the tabular data model (Stage 1.2)."""

from __future__ import annotations

from locus_engine.provenance import Provenance, SourceLocation
from locus_engine.table import TABLE_SCHEMA_VERSION, Cell, ProvenancedTable, Row


def _cell(col: str, value: object) -> Cell:
    return Cell(
        column=col,
        value=value,
        provenance=Provenance(locations=[SourceLocation(source_id="s", index=0)]),
    )


def test_cell_has_identity_and_provenance() -> None:
    c = _cell("total", 42)
    assert c.cell_id
    assert c.column == "total"
    assert c.value == 42
    assert c.provenance.locations[0].source_id == "s"


def test_row_value_dict_drops_provenance() -> None:
    row = Row(cells={"a": _cell("a", 1), "b": _cell("b", "x")})
    assert row.value_dict() == {"a": 1, "b": "x"}


def test_table_schema_version_constant() -> None:
    t = ProvenancedTable(columns=["a"])
    assert t.schema_version == TABLE_SCHEMA_VERSION == "table/v1"
    assert t.produced_by_engine == "deterministic"


def test_table_value_records() -> None:
    t = ProvenancedTable(
        columns=["a", "b"],
        rows=[
            Row(cells={"a": _cell("a", 1), "b": _cell("b", 2)}),
            Row(cells={"a": _cell("a", 3), "b": _cell("b", 4)}),
        ],
    )
    assert t.value_records() == [{"a": 1, "b": 2}, {"a": 3, "b": 4}]


def test_ids_unique_across_cells_and_rows() -> None:
    c1, c2 = _cell("a", 1), _cell("a", 1)
    assert c1.cell_id != c2.cell_id
    r1, r2 = Row(cells={"a": c1}), Row(cells={"a": c2})
    assert r1.row_id != r2.row_id
