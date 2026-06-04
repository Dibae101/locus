"""Tests for the CSV parser and router (Stage 3.2)."""

from __future__ import annotations

import pytest

from locus_engine.errors import ParserUnavailableError, RoutingError
from locus_engine.ir import IRElementKind
from locus_engine.parsers.csv_parser import CsvParser
from locus_engine.parsers.router import ParserRouter
from locus_engine.plugins import Parser, RawSource
from locus_engine.registry import PluginRegistry


def _raw(content_type: str = "text/csv") -> RawSource:
    return RawSource(
        source_id="s1",
        content_type=content_type,
        data=b"a,b\n1,2\n3,4\n",
    )


def test_csv_parser_produces_located_table() -> None:
    ir = CsvParser().parse(_raw())
    tables = ir.tables()
    assert len(tables) == 1
    el = tables[0]
    assert el.kind is IRElementKind.TABLE
    assert el.table is not None
    assert el.table.cells == [["a", "b"], ["1", "2"], ["3", "4"]]
    assert el.location.source_id == "s1"
    assert el.location.char_span is not None


def test_router_selects_by_content_type() -> None:
    reg = PluginRegistry()
    reg.register(CsvParser(), Parser)
    router = ParserRouter(reg)
    assert router.route(_raw()).name == "csv"


def test_router_unknown_content_type_raises_routing_error() -> None:
    reg = PluginRegistry()
    reg.register(CsvParser(), Parser)
    router = ParserRouter(reg)
    with pytest.raises(RoutingError):
        router.route(_raw(content_type="application/octet-stream"))


def test_router_no_parser_for_type_raises_routing_error() -> None:
    reg = PluginRegistry()
    reg.register(CsvParser(), Parser)
    router = ParserRouter(reg)
    with pytest.raises(RoutingError):
        router.route(_raw(content_type="application/pdf"))


def test_router_configured_unavailable_parser_is_run_fatal() -> None:
    """Req 2.4."""
    reg = PluginRegistry()
    reg.register(CsvParser(), Parser)
    router = ParserRouter(reg, overrides={"text/csv": "docling"})
    with pytest.raises(ParserUnavailableError):
        router.route(_raw())
