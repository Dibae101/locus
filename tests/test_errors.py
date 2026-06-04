"""Tests for the typed error hierarchy (Stage 0.2)."""

from __future__ import annotations

import pytest

from locus_engine.errors import (
    ConnectorError,
    LocusError,
    ParserUnavailableError,
    RegistrationError,
    SourceError,
    UnsupportedSourceError,
)


def test_all_errors_derive_from_locus_error() -> None:
    for exc in (
        ConnectorError("s1", "boom"),
        UnsupportedSourceError("s2", "no connector"),
        ParserUnavailableError("docling"),
        RegistrationError("MyPlugin", ["parse"]),
    ):
        assert isinstance(exc, LocusError)


def test_source_error_carries_source_id_and_reason() -> None:
    err = ConnectorError("doc-1", "file not found")
    assert err.source_id == "doc-1"
    assert err.reason == "file not found"
    assert "doc-1" in str(err)
    assert "file not found" in str(err)


def test_source_error_is_subclass_relationship() -> None:
    assert issubclass(ConnectorError, SourceError)
    assert issubclass(UnsupportedSourceError, SourceError)


def test_registration_error_lists_missing_methods() -> None:
    err = RegistrationError("BadParser", ["parse", "supports"])
    assert err.plugin_name == "BadParser"
    assert err.missing_methods == ["parse", "supports"]
    assert "parse" in str(err)
    assert "supports" in str(err)


def test_parser_unavailable_is_run_fatal_not_source_scoped() -> None:
    err = ParserUnavailableError("camelot")
    assert isinstance(err, LocusError)
    assert not isinstance(err, SourceError)
    assert "camelot" in str(err)


def test_can_catch_broadly() -> None:
    with pytest.raises(LocusError):
        raise ConnectorError("s", "r")
