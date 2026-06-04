"""Tests for the provenance conformance harness (Stage 4).

Encodes Properties 1-5 and 8 as automated checks and runs them against the built-in
components to prove they propagate provenance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from locus_engine.composer import ProvenanceComposer
from locus_engine.conformance import (
    ConformanceError,
    assert_mask_preserves_grounding,
    assert_merge_retains_locations,
    assert_table_provenance_survives,
    assert_value_change_triggers_regrounding,
    make_seeded_cell,
    probe_extraction_engine,
)
from locus_engine.connectors.files import FileConnector
from locus_engine.extract.deterministic import DeterministicEngine
from locus_engine.lineage import InMemoryLineageStore
from locus_engine.parsers.csv_parser import CsvParser
from locus_engine.plugins import ExtractContext, ResolvedSchema, SourceRef
from locus_engine.provenance import Provenance
from locus_engine.table import Cell, ProvenancedTable, Row

FIXTURES = Path(__file__).parent / "fixtures"


def test_merge_retention_property() -> None:
    a = make_seeded_cell("Jon", "doc-A")
    b = make_seeded_cell("Jonathan", "doc-B")
    merged = ProvenanceComposer.merge_cells([a, b], "Jonathan", strategy="longest")
    assert_merge_retains_locations([a, b], merged)


def test_mask_preservation_property() -> None:
    src = make_seeded_cell("123-45-6789", "doc-A")
    src.provenance.faithfulness = 0.9
    masked = ProvenanceComposer.mask_cell(src, "***")
    assert_mask_preserves_grounding(src, masked)


def test_value_change_regrounding_property() -> None:
    src = make_seeded_cell("100", "doc-A")
    mapped = ProvenanceComposer.map_cell(src, 100)
    assert_value_change_triggers_regrounding(src, mapped)


def test_harness_detects_dropped_lineage() -> None:
    """A cell with no resolvable origin must fail the harness."""
    orphan = Cell(column="c", value="x", provenance=Provenance(locations=[]))
    table = ProvenancedTable(columns=["c"], rows=[Row(cells={"c": orphan})])
    store = InMemoryLineageStore()
    store.put(orphan)
    with pytest.raises(ConformanceError):
        assert_table_provenance_survives(table, store)


def test_builtin_deterministic_engine_is_conformant() -> None:
    """The real file -> csv -> extract path must produce conformant provenance."""
    raw = FileConnector().read(SourceRef(uri=str(FIXTURES / "invoices.csv"), kind="file"))
    ir = CsvParser().parse(raw)
    schema = ResolvedSchema(mode="infer")
    probe_extraction_engine(
        DeterministicEngine(), ir, schema, ExtractContext(schema=schema)
    )
