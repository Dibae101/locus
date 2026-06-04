"""Golden end-to-end test for the deterministic vertical slice (Stage 3.7).

file -> CSV parse -> deterministic extract -> degraded grounding -> emit, with
provenance resolvable to source locations and a corpus summary event.

Covers Properties 1, 8, 9.
"""

from __future__ import annotations

from pathlib import Path

from locus_engine.config import PipelineConfig
from locus_engine.connectors.files import FileConnector
from locus_engine.emit.common import LINEAGE_COLUMN
from locus_engine.parsers.csv_parser import CsvParser
from locus_engine.pipeline import Pipeline
from locus_engine.plugins import Connector, Parser, SourceRef
from locus_engine.registry import PluginRegistry

FIXTURES = Path(__file__).parent / "fixtures"


def _registry() -> PluginRegistry:
    reg = PluginRegistry()
    reg.register(FileConnector(), Connector)
    reg.register(CsvParser(), Parser)
    return reg


def test_vertical_slice_end_to_end() -> None:
    cfg = PipelineConfig.load(
        {"source": {"type": "files", "path": str(FIXTURES)}, "grounding_threshold": 0.0}
    )
    pipeline = Pipeline(cfg, _registry())
    ref = SourceRef(uri=str(FIXTURES / "invoices.csv"), kind="file")

    out = pipeline.run([ref])

    # Table content (Property 9: stable schema version).
    assert out.table.schema_version == "table/v1"
    assert out.table.columns == ["invoice_number", "vendor", "total"]
    assert out.result.rows_emitted == 3
    assert out.result.corpus_success is True

    # Provenance survival (Property 1): each cell resolves to the source file.
    first_cell = out.table.rows[0].cells["invoice_number"]
    origins = out.lineage.resolve_origins(first_cell.cell_id)
    assert origins and origins[0].source_id.endswith("invoices.csv")

    # Emit carries the lineage column.
    frame = pipeline.emit(out)
    assert LINEAGE_COLUMN in frame.columns
    assert len(frame) == 3


def test_per_source_isolation_continues_after_bad_source() -> None:
    """Property 8: a missing source records an error; the good one still emits."""
    cfg = PipelineConfig.load(
        {"source": {"type": "files", "path": str(FIXTURES)}, "grounding_threshold": 0.0}
    )
    pipeline = Pipeline(cfg, _registry())
    refs = [
        SourceRef(uri=str(FIXTURES / "missing.csv"), kind="file"),
        SourceRef(uri=str(FIXTURES / "invoices.csv"), kind="file"),
    ]
    out = pipeline.run(refs)
    assert out.result.corpus_success is True
    assert len(out.result.errored) == 1
    assert out.result.rows_emitted == 3
