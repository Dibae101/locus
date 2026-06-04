"""Tests for the file connector (Stage 3.1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from locus_engine.connectors.files import FileConnector, detect_content_type
from locus_engine.errors import ConnectorError
from locus_engine.plugins import SourceRef

FIXTURES = Path(__file__).parent / "fixtures"


def test_detect_content_type_csv() -> None:
    assert detect_content_type(FIXTURES / "invoices.csv") == "text/csv"


def test_reads_existing_file() -> None:
    conn = FileConnector()
    ref = SourceRef(uri=str(FIXTURES / "invoices.csv"))
    assert conn.supports(ref)
    raw = conn.read(ref)
    assert raw.content_type == "text/csv"
    assert raw.data is not None and b"INV-1001" in raw.data
    assert raw.source_id.endswith("invoices.csv")


def test_missing_file_raises_connector_error() -> None:
    conn = FileConnector()
    with pytest.raises(ConnectorError) as ei:
        conn.read(SourceRef(uri=str(FIXTURES / "nope.csv"), kind="file"))
    assert "file not found" in ei.value.reason
