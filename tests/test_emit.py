"""Tests for emitters (Stage 3.5)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from locus_engine.emit.common import LINEAGE_COLUMN
from locus_engine.emit.dataframe import DataFrameEmitter
from locus_engine.emit.parquet import ParquetEmitter
from locus_engine.errors import EmitError
from locus_engine.provenance import GroundingMode, Provenance, SourceLocation
from locus_engine.table import Cell, ProvenancedTable, Row


def _table() -> ProvenancedTable:
    loc = SourceLocation(source_id="s1", index=0)
    cell = Cell(
        column="vendor",
        value="Acme",
        provenance=Provenance(
            locations=[loc],
            faithfulness=0.9,
            grounding_mode=GroundingMode.DEGRADED,
        ),
    )
    return ProvenancedTable(columns=["vendor"], rows=[Row(cells={"vendor": cell})])


def test_dataframe_has_lineage_column_and_engine_attr() -> None:
    frame = DataFrameEmitter().to_frame(_table())
    assert LINEAGE_COLUMN in frame.columns
    assert frame.attrs["produced_by_engine"] == "deterministic"
    lineage = frame.iloc[0][LINEAGE_COLUMN]
    assert lineage["vendor"]["faithfulness"] == 0.9
    assert lineage["vendor"]["locations"][0]["source_id"] == "s1"


def test_empty_result_writes_schema_columns_zero_rows() -> None:
    """Req 8.2."""
    empty = ProvenancedTable(columns=["vendor", "total"])
    frame = DataFrameEmitter().to_frame(empty)
    assert list(frame.columns) == ["vendor", "total", LINEAGE_COLUMN]
    assert len(frame) == 0


def test_parquet_round_trip(tmp_path: Path) -> None:
    dest = tmp_path / "out.parquet"
    res = ParquetEmitter().emit(_table(), str(dest))
    assert res.rows_written == 1
    back = pd.read_parquet(dest)
    assert "vendor" in back.columns and LINEAGE_COLUMN in back.columns


def test_parquet_inaccessible_destination_raises_emit_error() -> None:
    """Req 8.7."""
    with pytest.raises(EmitError):
        ParquetEmitter().emit(_table(), "/no/such/dir/out.parquet")
