"""Tests for the plugin registry (Stage 2.2)."""

from __future__ import annotations

import pytest

from locus_engine.errors import RegistrationError
from locus_engine.ir import IntermediateRepresentation
from locus_engine.plugins import Parser, RawSource
from locus_engine.registry import PluginRegistry


class GoodParser:
    name = "good"
    content_types = ("application/pdf",)

    def supports(self, content_type: str) -> bool:
        return content_type in self.content_types

    def parse(self, raw: RawSource) -> IntermediateRepresentation:
        return IntermediateRepresentation(source_id=raw.source_id, content_type=raw.content_type)


class OverridePdfParser(GoodParser):
    name = "override"


class IncompleteParser:
    name = "incomplete"
    content_types = ("application/pdf",)

    def supports(self, content_type: str) -> bool:
        return True

    # missing parse()


def test_register_valid_parser() -> None:
    reg = PluginRegistry()
    reg.register(GoodParser(), Parser)
    assert reg.names(Parser) == ["good"]


def test_reject_incomplete_plugin_lists_missing_methods() -> None:
    """Req 10.4."""
    reg = PluginRegistry()
    with pytest.raises(RegistrationError) as ei:
        reg.register(IncompleteParser(), Parser)
    assert "parse" in ei.value.missing_methods
    assert "IncompleteParser" in str(ei.value)


def test_parser_resolution_by_content_type() -> None:
    reg = PluginRegistry()
    reg.register(GoodParser(), Parser)
    assert reg.parser_for("application/pdf").name == "good"
    with pytest.raises(LookupError):
        reg.parser_for("text/csv")


def test_config_override_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Req 10.5: a config-named parser is selected over the default."""
    reg = PluginRegistry()
    reg.register(GoodParser(), Parser)
    reg.register(OverridePdfParser(), Parser)
    assert reg.parser_for("application/pdf", override="override").name == "override"


def test_override_missing_raises() -> None:
    reg = PluginRegistry()
    reg.register(GoodParser(), Parser)
    with pytest.raises(LookupError):
        reg.parser_for("application/pdf", override="nope")
