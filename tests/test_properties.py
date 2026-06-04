"""Consolidated correctness-property suite (Stage 10.1).

Encodes the nine design correctness properties as explicit, CI-runnable checks over
the real built-in components. This is the regression guard for the engine's core
guarantees.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from locus_engine.composer import ProvenanceComposer
from locus_engine.config import PipelineConfig
from locus_engine.conformance import (
    assert_faithfulness_bounds,
    assert_mask_preserves_grounding,
    assert_merge_retains_locations,
    assert_table_provenance_survives,
    assert_value_change_triggers_regrounding,
    make_seeded_cell,
)
from locus_engine.connectors.files import FileConnector
from locus_engine.extract.dual import Extractor
from locus_engine.ir import IR_SCHEMA_VERSION
from locus_engine.llm.engine import LLMEngine
from locus_engine.parsers.csv_parser import CsvParser
from locus_engine.pipeline import Pipeline
from locus_engine.plugins import Connector, Parser, ResolvedSchema, SourceRef
from locus_engine.registry import PluginRegistry
from locus_engine.table import TABLE_SCHEMA_VERSION

FIXTURES = Path(__file__).parent / "fixtures"


def _registry() -> PluginRegistry:
    reg = PluginRegistry()
    reg.register(FileConnector(), Connector)
    reg.register(CsvParser(), Parser)
    return reg


def _run() -> Any:
    cfg = PipelineConfig.load(
        {"source": {"type": "files", "path": str(FIXTURES)}, "grounding_threshold": 0.0}
    )
    return Pipeline(cfg, _registry()).run(
        [SourceRef(uri=str(FIXTURES / "invoices.csv"), kind="file")]
    )


def test_property_1_provenance_survival() -> None:
    out = _run()
    assert_table_provenance_survives(out.table, out.lineage)


def test_property_2_faithfulness_bounds() -> None:
    out = _run()
    assert_faithfulness_bounds(out.table, validated=True)


def test_property_3_merge_location_retention() -> None:
    a = make_seeded_cell("X", "doc-A")
    b = make_seeded_cell("Y", "doc-B")
    merged = ProvenanceComposer.merge_cells([a, b], "X", strategy="first")
    assert_merge_retains_locations([a, b], merged)


def test_property_4_mask_preserves_grounding() -> None:
    c = make_seeded_cell("secret", "doc-A")
    c.provenance.faithfulness = 0.8
    assert_mask_preserves_grounding(c, ProvenanceComposer.mask_cell(c, "***"))


def test_property_5_value_change_triggers_regrounding() -> None:
    c = make_seeded_cell("1", "doc-A")
    assert_value_change_triggers_regrounding(c, ProvenanceComposer.map_cell(c, 1))


def test_property_6_llm_non_override(monkeypatch) -> None:
    def mapper(raw: dict[str, Any], schema: ResolvedSchema) -> dict[str, Any]:
        return {k: "OVERRIDE" for k in raw}

    raw = FileConnector().read(SourceRef(uri=str(FIXTURES / "invoices.csv"), kind="file"))
    ir = CsvParser().parse(raw)
    from locus_engine.plugins import ExtractContext

    extractor = Extractor(llm=LLMEngine(field_mapper=mapper))
    table = extractor.extract(
        ir,
        ResolvedSchema(mode="infer"),
        ExtractContext(schema=ResolvedSchema(mode="infer"), credential_available=True),
    )
    # deterministic values kept; every row flagged because LLM tried to override
    assert all(r.flagged for r in table.rows)
    assert table.rows[0].cells["vendor"].value != "OVERRIDE"


def test_property_7_no_egress_without_credential() -> None:
    """A run with no credential must never construct/activate the LLM path."""
    out = _run()
    assert out.table.produced_by_engine == "deterministic"


def test_property_8_per_source_isolation() -> None:
    cfg = PipelineConfig.load(
        {"source": {"type": "files", "path": str(FIXTURES)}, "grounding_threshold": 0.0}
    )
    out = Pipeline(cfg, _registry()).run(
        [
            SourceRef(uri=str(FIXTURES / "missing.csv"), kind="file"),
            SourceRef(uri=str(FIXTURES / "invoices.csv"), kind="file"),
        ]
    )
    assert out.result.corpus_success is True
    assert len(out.result.errored) == 1


def test_property_9_schema_version_stability() -> None:
    out = _run()
    assert out.table.schema_version == TABLE_SCHEMA_VERSION == "table/v1"
    assert IR_SCHEMA_VERSION == "ir/v1"
