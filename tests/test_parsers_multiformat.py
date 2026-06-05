"""Tests for the multi-format parsers and the document-elements fallback.

Office/OpenDocument/EPUB/ZIP fixtures are built in-memory as ZIP+XML so the tests
have no third-party dependencies and no external files.
"""

from __future__ import annotations

import io
import zipfile

import pytest

from locus_engine.errors import ParserError
from locus_engine.extract.deterministic import DeterministicEngine
from locus_engine.parsers.archive import ArchiveParser
from locus_engine.parsers.image import ImageParser
from locus_engine.parsers.json_parser import JsonParser
from locus_engine.parsers.markdown import MarkdownParser
from locus_engine.parsers.office import DocxParser, OdtParser, PptxParser, XlsxParser
from locus_engine.parsers.text import TextParser
from locus_engine.plugins import ExtractContext, RawSource, ResolvedSchema


def _raw(data: bytes, content_type: str, source_id: str = "s") -> RawSource:
    return RawSource(source_id=source_id, content_type=content_type, data=data)


# --- markdown -------------------------------------------------------------


def test_markdown_pipe_table() -> None:
    md = b"""# Title

| name | amount |
|------|-------:|
| Acme | 100    |
| Globex | 200  |

Some trailing prose.
"""
    ir = MarkdownParser().parse(_raw(md, "text/markdown"))
    tables = ir.tables()
    assert len(tables) == 1
    grid = tables[0].table.cells
    assert grid[0] == ["name", "amount"]
    assert grid[1] == ["Acme", "100"]
    assert grid[2] == ["Globex", "200"]


def test_markdown_without_table_has_text() -> None:
    ir = MarkdownParser().parse(_raw(b"# Heading\n\nJust prose, no table.", "text/markdown"))
    assert not ir.tables()
    assert any(e.text for e in ir.elements)


# --- json -----------------------------------------------------------------


def test_json_array_of_objects() -> None:
    data = b'[{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]'
    ir = JsonParser().parse(_raw(data, "application/json"))
    grid = ir.tables()[0].table.cells
    assert grid[0] == ["a", "b"]
    assert grid[1] == ["1", "x"]


def test_json_nested_object_flattens() -> None:
    data = b'{"name": "app", "action": {"title": "X", "icon": "i.png"}, "perms": ["a", "b"]}'
    ir = JsonParser().parse(_raw(data, "application/json"))
    grid = ir.tables()[0].table.cells
    keys = [r[0] for r in grid[1:]]
    assert "action.title" in keys
    assert "perms[0]" in keys


def test_json_from_records() -> None:
    raw = RawSource(
        source_id="api", content_type="application/json",
        records=[{"x": 1}, {"x": 2}],
    )
    ir = JsonParser().parse(raw)
    grid = ir.tables()[0].table.cells
    assert grid[0] == ["x"]
    assert len(grid) == 3


# --- text -----------------------------------------------------------------


def test_text_splits_paragraphs() -> None:
    ir = TextParser().parse(_raw(b"Para one.\n\nPara two.", "text/plain"))
    assert len(ir.elements) == 2
    assert ir.elements[0].text == "Para one."


# --- office (built in-memory) ---------------------------------------------


def _docx(paragraphs: list[str], table: list[list[str]] | None = None) -> bytes:
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body_parts = []
    for p in paragraphs:
        body_parts.append(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>")
    if table:
        rows = ""
        for row in table:
            cells = "".join(
                f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in row
            )
            rows += f"<w:tr>{cells}</w:tr>"
        body_parts.append(f"<w:tbl>{rows}</w:tbl>")
    doc = (
        f'<?xml version="1.0"?><w:document xmlns:w="{ns}"><w:body>'
        + "".join(body_parts)
        + "</w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", doc)
    return buf.getvalue()


def test_docx_paragraphs_and_table() -> None:
    data = _docx(["Hello world"], table=[["h1", "h2"], ["a", "b"]])
    ct = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ir = DocxParser().parse(_raw(data, ct))
    assert any(e.text == "Hello world" for e in ir.elements)
    tables = ir.tables()
    assert tables and tables[0].table.cells[0] == ["h1", "h2"]


def _xlsx(rows: list[list[str]]) -> bytes:
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    body = ""
    for r in rows:
        cells = "".join(f'<c t="inlineStr"><is><t>{v}</t></is></c>' for v in r)
        body += f"<row>{cells}</row>"
    sheet = (
        f'<?xml version="1.0"?><worksheet xmlns="{ns}"><sheetData>{body}'
        "</sheetData></worksheet>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()


def test_xlsx_inline_strings() -> None:
    data = _xlsx([["name", "qty"], ["Acme", "3"]])
    ct = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ir = XlsxParser().parse(_raw(data, ct))
    grid = ir.tables()[0].table.cells
    assert grid[0] == ["name", "qty"]
    assert grid[1] == ["Acme", "3"]


def _odt(paragraphs: list[str]) -> bytes:
    text_ns = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    office_ns = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    body = "".join(f"<text:p>{p}</text:p>" for p in paragraphs)
    content = (
        f'<?xml version="1.0"?><office:document-content '
        f'xmlns:office="{office_ns}" xmlns:text="{text_ns}">'
        f"<office:body><office:text>{body}</office:text></office:body>"
        "</office:document-content>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("content.xml", content)
    return buf.getvalue()


def test_odt_text() -> None:
    data = _odt(["First para", "Second para"])
    ir = OdtParser().parse(_raw(data, "application/vnd.oasis.opendocument.text"))
    assert any(e.text == "First para" for e in ir.elements)


def _pptx_slide(texts: list[str]) -> bytes:
    a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    runs = "".join(f"<a:p><a:r><a:t>{t}</a:t></a:r></a:p>" for t in texts)
    slide = f'<?xml version="1.0"?><a:sld xmlns:a="{a_ns}">{runs}</a:sld>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("ppt/slides/slide1.xml", slide)
    return buf.getvalue()


def test_pptx_text() -> None:
    data = _pptx_slide(["Bullet one", "Bullet two"])
    ct = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ir = PptxParser().parse(_raw(data, ct))
    assert any(e.text == "Bullet one" for e in ir.elements)


# --- archive --------------------------------------------------------------


def test_archive_merges_member_elements() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.csv", "name,amount\nAcme,100\n")
        zf.writestr("notes.txt", "some notes")
        zf.writestr("logo.bin", b"\x00\x01\x02")  # skipped, no parser
    ir = ArchiveParser().parse(_raw(buf.getvalue(), "application/zip"))
    assert ir.tables()  # csv member produced a table
    assert any("a.csv" in (e.location.note or "") for e in ir.elements)


# --- image (clear OCR error) ----------------------------------------------


def test_image_parser_raises_ocr_guidance() -> None:
    with pytest.raises(ParserError) as exc:
        ImageParser().parse(_raw(b"\x89PNG", "image/png"))
    assert "OCR" in str(exc.value)


# --- document-elements fallback -------------------------------------------


def test_elements_fallback_turns_prose_into_table() -> None:
    """A document with text but no grid yields a (element|text|location) table
    instead of erroring, with each cell grounded to the element's location."""
    ir = TextParser().parse(_raw(b"First para.\n\nSecond para.", "text/plain"))
    schema = ResolvedSchema(mode="infer")
    table = DeterministicEngine().extract(ir, schema, ExtractContext(schema=schema))
    assert table.columns == ["element", "text", "location"]
    assert len(table.rows) == 2
    first = table.rows[0]
    assert first.cells["text"].value == "First para."
    # provenance present on every cell
    assert all(c.provenance.locations for c in first.cells.values())
