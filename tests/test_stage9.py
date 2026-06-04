"""Tests for Stage 9 connectors, parsers, and the SQL emitter."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from locus_engine.connectors.http import HttpConnector, RestApiConnector
from locus_engine.connectors.sql import SqlConnector
from locus_engine.emit.common import LINEAGE_COLUMN
from locus_engine.emit.sql import SqlEmitter
from locus_engine.errors import ConnectorError, EmitError
from locus_engine.parsers.html import HtmlParser
from locus_engine.parsers.records import RecordsParser
from locus_engine.plugins import RawSource, SourceRef
from locus_engine.provenance import Provenance, SourceLocation
from locus_engine.table import Cell, ProvenancedTable, Row

# --- records parser -------------------------------------------------------


def test_records_parser_builds_table() -> None:
    raw = RawSource(
        source_id="api#1",
        content_type="application/json",
        records=[{"name": "Acme", "amount": 100}, {"name": "Globex", "amount": 200}],
    )
    ir = RecordsParser().parse(raw)
    table = ir.tables()[0].table
    assert table is not None
    assert table.cells[0] == ["name", "amount"]
    assert table.cells[1] == ["Acme", "100"]


def test_records_parser_unions_keys() -> None:
    raw = RawSource(
        source_id="api#1",
        content_type="application/json",
        records=[{"a": 1}, {"b": 2}],
    )
    ir = RecordsParser().parse(raw)
    assert ir.tables()[0].table.cells[0] == ["a", "b"]


# --- html parser ----------------------------------------------------------


def test_html_parser_extracts_text_and_tables() -> None:
    html = b"""
    <html><body>
      <h1>Title</h1>
      <p>Some text</p>
      <table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table>
      <script>ignore()</script>
    </body></html>
    """
    raw = RawSource(source_id="page", content_type="text/html", data=html)
    ir = HtmlParser().parse(raw)
    texts = [e.text for e in ir.elements if e.text]
    assert "Title" in texts
    assert "Some text" in texts
    tables = ir.tables()
    assert tables and tables[0].table.cells == [["a", "b"], ["1", "2"]]


# --- connectors -----------------------------------------------------------


def test_http_connector_supports_url() -> None:
    conn = HttpConnector()
    assert conn.supports(SourceRef(uri="https://example.com"))
    assert not conn.supports(SourceRef(uri="/local/path", kind="file"))


def test_rest_connector_extracts_records() -> None:
    conn = RestApiConnector(records_path="data")

    def fake_extract(payload: object) -> object:  # not used; we test _extract_records
        return payload

    records = conn._extract_records({"data": [{"x": 1}, {"x": 2}]})  # noqa: SLF001
    assert records == [{"x": 1}, {"x": 2}]


def test_sql_connector_reads_rows(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE v (name TEXT, amount INTEGER)")
    conn.execute("INSERT INTO v VALUES ('Acme', 100), ('Globex', 200)")
    conn.commit()
    conn.close()

    connector = SqlConnector(query="SELECT * FROM v ORDER BY name")
    raw = connector.read(SourceRef(uri=str(db), kind="sql"))
    assert raw.records == [
        {"name": "Acme", "amount": 100},
        {"name": "Globex", "amount": 200},
    ]


def test_sql_connector_bad_query_raises(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    sqlite3.connect(db).close()
    connector = SqlConnector(query="SELECT * FROM nope")
    with pytest.raises(ConnectorError):
        connector.read(SourceRef(uri=str(db), kind="sql"))


# --- sql emitter ----------------------------------------------------------


def _table() -> ProvenancedTable:
    loc = SourceLocation(source_id="s1", index=0)
    cell = Cell(
        column="vendor",
        value="Acme",
        provenance=Provenance(locations=[loc], faithfulness=0.9),
    )
    return ProvenancedTable(columns=["vendor"], rows=[Row(cells={"vendor": cell})])


def test_sql_emitter_writes_rows_with_lineage(tmp_path: Path) -> None:
    dest = tmp_path / "out.db"
    res = SqlEmitter().emit(_table(), str(dest))
    assert res.rows_written == 1
    conn = sqlite3.connect(dest)
    rows = conn.execute("SELECT * FROM locus_output").fetchall()
    cols = [d[0] for d in conn.execute("SELECT * FROM locus_output").description]
    conn.close()
    assert LINEAGE_COLUMN in cols
    assert rows[0][0] == "Acme"


def test_sql_emitter_empty_creates_table(tmp_path: Path) -> None:
    dest = tmp_path / "out.db"
    res = SqlEmitter().emit(ProvenancedTable(columns=["vendor"]), str(dest))
    assert res.rows_written == 0
    conn = sqlite3.connect(dest)
    cols = [d[0] for d in conn.execute("SELECT * FROM locus_output").description]
    conn.close()
    assert "vendor" in cols and LINEAGE_COLUMN in cols


def test_sql_emitter_bad_destination_raises() -> None:
    with pytest.raises(EmitError):
        SqlEmitter().emit(_table(), "/no/such/dir/out.db")
