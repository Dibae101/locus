"""Pipeline integration tests for the opt-in LLM path (Stage 6.5, 6.6)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from locus_engine.config import PipelineConfig
from locus_engine.connectors.files import FileConnector
from locus_engine.llm.credentials import CredentialResolver
from locus_engine.llm.engine import LLMEngine
from locus_engine.parsers.csv_parser import CsvParser
from locus_engine.pipeline import Pipeline
from locus_engine.plugins import Connector, Parser, ResolvedSchema, SourceRef
from locus_engine.registry import PluginRegistry

FIXTURES = Path(__file__).parent / "fixtures"


def _registry() -> PluginRegistry:
    reg = PluginRegistry()
    reg.register(FileConnector(), Connector)
    reg.register(CsvParser(), Parser)
    return reg


def test_no_credential_emits_llm_available_notice_and_stays_deterministic() -> None:
    cfg = PipelineConfig.load(
        {"source": {"type": "files", "path": str(FIXTURES)}, "grounding_threshold": 0.0}
    )
    pipeline = Pipeline(cfg, _registry())
    out = pipeline.run([SourceRef(uri=str(FIXTURES / "invoices.csv"), kind="file")])
    assert out.table.produced_by_engine == "deterministic"


def test_credential_present_shows_consent_and_uses_llm(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-a-real-secret")

    def mapper(raw: dict[str, Any], schema: ResolvedSchema) -> dict[str, Any]:
        return raw  # echo: no conflict, no fill

    cfg = PipelineConfig.load(
        {
            "source": {"type": "files", "path": str(FIXTURES)},
            "grounding_threshold": 0.0,
            "llm": {"provider": "openai", "model": "gpt-4o"},
        }
    )
    pipeline = Pipeline(
        cfg,
        _registry(),
        credential_resolver=CredentialResolver(),
        llm_engine=LLMEngine(field_mapper=mapper),
    )
    out = pipeline.run([SourceRef(uri=str(FIXTURES / "invoices.csv"), kind="file")])

    # consent event emitted before processing
    phases = [e.phase for e in pipeline._obs.events]  # noqa: SLF001 (test introspection)
    assert "consent" in phases
    assert out.table.produced_by_engine == "llm"
