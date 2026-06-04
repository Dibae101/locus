"""Pipeline integration test for clean + dedup phases (Stage 5)."""

from __future__ import annotations

from pathlib import Path

from locus_engine.config import PipelineConfig
from locus_engine.connectors.files import FileConnector
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


def test_pipeline_dedupes_when_enabled() -> None:
    cfg = PipelineConfig.load(
        {
            "source": {"type": "files", "path": str(FIXTURES)},
            "grounding_threshold": 0.0,
            "dedup": {"enabled": True, "keys": ["name", "city"]},
        }
    )
    pipeline = Pipeline(cfg, _registry())
    out = pipeline.run([SourceRef(uri=str(FIXTURES / "dupes.csv"), kind="file")])
    # 3 rows in, 2 distinct entities out (Acme x2 merged).
    assert out.table.columns == ["name", "city"]
    assert len(out.table.rows) == 2


def test_infer_mode_auto_coerces_numeric_values() -> None:
    """Stage 7: infer mode infers column types and the cleaner coerces them."""
    cfg = PipelineConfig.load(
        {"source": {"type": "files", "path": str(FIXTURES)}, "grounding_threshold": 0.0}
    )
    pipeline = Pipeline(cfg, _registry())
    out = pipeline.run([SourceRef(uri=str(FIXTURES / "invoices.csv"), kind="file")])
    # 'total' column should be coerced to float by inferred typing.
    total = out.table.rows[0].cells["total"].value
    assert isinstance(total, float)
    assert total == 250.0
