"""Tests for the optional LLM engine, router, credentials, and reconciler (Stage 6).

All LLM interaction is mocked; Property 7 (no egress without a credential) is
asserted explicitly.
"""

from __future__ import annotations

from typing import Any

import pytest

from locus_engine.errors import ConfigError, ExtractionError
from locus_engine.extract.dual import Extractor
from locus_engine.ir import (
    IntermediateRepresentation,
    IRElement,
    IRElementKind,
    IRTable,
)
from locus_engine.llm.credentials import (
    CredentialResolver,
    assert_no_raw_key_in_config,
    looks_like_raw_key,
)
from locus_engine.llm.engine import LLMEngine
from locus_engine.llm.router import ProviderRouter
from locus_engine.plugins import ExtractContext, ResolvedSchema
from locus_engine.provenance import Provenance, SourceLocation
from locus_engine.table import Cell, ProvenancedTable, Row

# --- credentials (6.1) ----------------------------------------------------


def test_looks_like_raw_key() -> None:
    assert looks_like_raw_key("sk-abcdefghijklmnop1234567890")
    assert not looks_like_raw_key("${OPENAI_API_KEY}")


def test_raw_key_in_config_rejected() -> None:
    """Req 15.3."""
    with pytest.raises(ConfigError):
        assert_no_raw_key_in_config("sk-abcdefghijklmnop1234567890")
    # references are fine
    assert_no_raw_key_in_config("${OPENAI_API_KEY}")


def test_resolver_precedence_env_file_over_env(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=from-file\n")
    monkeypatch.setenv("OPENAI_API_KEY", "from-env")
    resolver = CredentialResolver(env_file=str(env_file))
    assert resolver.resolve("openai") == "from-file"


def test_resolver_env_fallback(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    resolver = CredentialResolver()
    assert resolver.resolve("anthropic") == "from-env"


def test_resolver_absent_is_none(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    resolver = CredentialResolver()
    assert resolver.resolve("openai") is None
    assert resolver.is_available("openai") is False


# --- router (6.2) ---------------------------------------------------------


def test_router_model_string_and_injected_fn() -> None:
    calls: list[dict[str, Any]] = []

    def fake_completion(*, model: str, messages: list[dict[str, str]], **kw: Any) -> Any:
        calls.append({"model": model, "messages": messages, **kw})
        return {"ok": True}

    router = ProviderRouter(completion_fn=fake_completion)
    assert router.model_string("openai", "gpt-4o") == "openai/gpt-4o"
    router.complete(
        provider="anthropic",
        model="claude",
        messages=[{"role": "user", "content": "x"}],
    )
    assert calls[0]["model"] == "anthropic/claude"


# --- engine (6.3) ---------------------------------------------------------


def _det_table_ir() -> IntermediateRepresentation:
    loc = SourceLocation(source_id="s1", index=0)
    grid = [["name", "amount"], ["Acme", ""]]
    el = IRElement(kind=IRElementKind.TABLE, table=IRTable(cells=grid, location=loc), location=loc)
    return IntermediateRepresentation(source_id="s1", content_type="text/csv", elements=[el])


def test_llm_engine_retries_then_fails_on_schema_violation() -> None:
    def bad_mapper(raw: dict[str, Any], schema: ResolvedSchema) -> dict[str, Any]:
        raise ValueError("never valid")

    engine = LLMEngine(field_mapper=bad_mapper)
    det = ProvenancedTable(
        columns=["name"],
        rows=[Row(cells={"name": Cell(column="name", value="", provenance=Provenance())})],
    )
    ctx = ExtractContext(schema=ResolvedSchema(), retry_limit=1)
    with pytest.raises(ExtractionError):
        engine.map_fields(det, ResolvedSchema(mode="infer"), ctx)


# --- dual-engine reconciliation (6.4) -------------------------------------


def test_no_credential_uses_deterministic_only_no_llm_called() -> None:
    """Property 7: with no credential, the LLM engine is never invoked."""
    called = {"llm": False}

    def mapper(raw: dict[str, Any], schema: ResolvedSchema) -> dict[str, Any]:
        called["llm"] = True
        return raw

    extractor = Extractor(llm=LLMEngine(field_mapper=mapper))
    ctx = ExtractContext(schema=ResolvedSchema(mode="infer"), credential_available=False)
    table = extractor.extract(_det_table_ir(), ResolvedSchema(mode="infer"), ctx)
    assert called["llm"] is False
    assert table.produced_by_engine == "deterministic"


def test_llm_fills_empty_cell() -> None:
    def mapper(raw: dict[str, Any], schema: ResolvedSchema) -> dict[str, Any]:
        out = dict(raw)
        if not out.get("amount"):
            out["amount"] = "250"
        return out

    extractor = Extractor(llm=LLMEngine(field_mapper=mapper))
    ctx = ExtractContext(schema=ResolvedSchema(mode="infer"), credential_available=True)
    table = extractor.extract(_det_table_ir(), ResolvedSchema(mode="infer"), ctx)
    row = table.rows[0]
    assert row.cells["amount"].value == "250"
    # filled value is marked for re-grounding
    assert row.cells["amount"].provenance.needs_regrounding is True


def test_llm_conflict_does_not_override_and_flags_row() -> None:
    """Property 6: LLM cannot override a deterministic value without flagging."""
    def mapper(raw: dict[str, Any], schema: ResolvedSchema) -> dict[str, Any]:
        return {"name": "DIFFERENT", "amount": raw.get("amount", "")}

    extractor = Extractor(llm=LLMEngine(field_mapper=mapper))
    ctx = ExtractContext(schema=ResolvedSchema(mode="infer"), credential_available=True)
    table = extractor.extract(_det_table_ir(), ResolvedSchema(mode="infer"), ctx)
    row = table.rows[0]
    assert row.cells["name"].value == "Acme"  # deterministic value kept
    assert row.flagged is True
