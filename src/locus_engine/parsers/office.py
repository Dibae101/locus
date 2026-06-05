"""Office Open XML + OpenDocument + EPUB parsers (dependency-free).

DOCX, PPTX, XLSX, ODT and EPUB are all ZIP archives of XML. These parsers read the
archive with the standard library (``zipfile`` + ``xml.etree``) and extract tables
and text, attaching ``SourceLocation`` provenance. No third-party libraries and no
network, so they live in the deterministic engine.

Namespaces vary across producers, so matching is done on the XML *local name*
(the tag after any ``{namespace}`` prefix) rather than fully-qualified names.

Requirements: 2.2, 3.1, 3.2, 3.3.
"""

from __future__ import annotations

import io
import zipfile
from xml.etree import ElementTree as ET

from locus_engine.errors import ParserError
from locus_engine.ir import (
    IntermediateRepresentation,
    IRElement,
    IRElementKind,
    IRTable,
)
from locus_engine.plugins import RawSource
from locus_engine.provenance import SourceLocation


def _local(tag: str) -> str:
    """Return an element's local name, dropping any ``{namespace}`` prefix."""
    return tag.rsplit("}", 1)[-1]


def _text_of(el: ET.Element) -> str:
    """Concatenate all descendant text, collapsing whitespace."""
    return " ".join(t.strip() for t in el.itertext() if t and t.strip())


def _open_zip(raw: RawSource) -> zipfile.ZipFile:
    if raw.data is None:
        raise ParserError(raw.source_id, "parser requires raw bytes")
    try:
        return zipfile.ZipFile(io.BytesIO(raw.data))
    except zipfile.BadZipFile as exc:
        raise ParserError(raw.source_id, f"not a valid archive: {exc}") from exc


def _finish(
    raw: RawSource, elements: list[IRElement], what: str
) -> IntermediateRepresentation:
    if not elements:
        raise ParserError(raw.source_id, f"no content extracted from {what}")
    return IntermediateRepresentation(
        source_id=raw.source_id, content_type=raw.content_type, elements=elements
    )


def _table_element(raw: RawSource, grid: list[list[str]], index: int, note: str) -> IRElement:
    loc = SourceLocation(source_id=raw.source_id, index=index, note=note)
    return IRElement(
        kind=IRElementKind.TABLE, table=IRTable(cells=grid, location=loc), location=loc
    )


def _text_element(raw: RawSource, text: str, heading: bool = False) -> IRElement:
    loc = SourceLocation(source_id=raw.source_id, index=0, note="text")
    kind = IRElementKind.HEADING if heading else IRElementKind.PARAGRAPH
    return IRElement(kind=kind, text=text, location=loc)


class DocxParser:
    """Word .docx: paragraphs + tables from word/document.xml."""

    name = "docx"
    content_types: tuple[str, ...] = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    def supports(self, content_type: str) -> bool:
        return content_type in self.content_types

    def parse(self, raw: RawSource) -> IntermediateRepresentation:
        with _open_zip(raw) as zf:
            try:
                xml = zf.read("word/document.xml")
            except KeyError as exc:
                raise ParserError(raw.source_id, "missing word/document.xml") from exc
        root = ET.fromstring(xml)  # noqa: S314 - local trusted office file
        body = next((c for c in root if _local(c.tag) == "body"), root)

        elements: list[IRElement] = []
        t_index = 0
        for child in body:
            name = _local(child.tag)
            if name == "tbl":
                grid = self._table_grid(child)
                if grid:
                    elements.append(_table_element(raw, grid, t_index, "docx table"))
                    t_index += 1
            elif name == "p":
                text = _text_of(child)
                if text:
                    elements.append(_text_element(raw, text))
        return _finish(raw, elements, "docx")

    def _table_grid(self, tbl: ET.Element) -> list[list[str]]:
        grid: list[list[str]] = []
        for tr in (c for c in tbl if _local(c.tag) == "tr"):
            row = [_text_of(tc) for tc in tr if _local(tc.tag) == "tc"]
            if row:
                grid.append(row)
        return self._rectangularize(grid)

    @staticmethod
    def _rectangularize(grid: list[list[str]]) -> list[list[str]]:
        if not grid:
            return grid
        width = max(len(r) for r in grid)
        return [r + [""] * (width - len(r)) for r in grid]


class PptxParser:
    """PowerPoint .pptx: text + tables across ppt/slides/slide*.xml."""

    name = "pptx"
    content_types: tuple[str, ...] = (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )

    def supports(self, content_type: str) -> bool:
        return content_type in self.content_types

    def parse(self, raw: RawSource) -> IntermediateRepresentation:
        with _open_zip(raw) as zf:
            slides = sorted(
                n for n in zf.namelist()
                if n.startswith("ppt/slides/slide") and n.endswith(".xml")
            )
            payloads = [(n, zf.read(n)) for n in slides]

        elements: list[IRElement] = []
        t_index = 0
        for slide_no, (_, xml) in enumerate(payloads, start=1):
            root = ET.fromstring(xml)  # noqa: S314 - local trusted office file
            elements.append(_text_element(raw, f"Slide {slide_no}", heading=True))
            for tbl in root.iter():
                if _local(tbl.tag) == "tbl":
                    grid = self._table_grid(tbl)
                    if grid:
                        elements.append(_table_element(raw, grid, t_index, "pptx table"))
                        t_index += 1
            # Text runs: each <a:p> paragraph is a line of slide text.
            for p in root.iter():
                if _local(p.tag) == "p":
                    text = " ".join(
                        t.text.strip()
                        for t in p.iter()
                        if _local(t.tag) == "t" and t.text and t.text.strip()
                    )
                    if text:
                        elements.append(_text_element(raw, text))
        return _finish(raw, elements, "pptx")

    @staticmethod
    def _table_grid(tbl: ET.Element) -> list[list[str]]:
        grid: list[list[str]] = []
        for tr in tbl.iter():
            if _local(tr.tag) != "tr":
                continue
            row = [_text_of(tc) for tc in tr if _local(tc.tag) == "tc"]
            if row:
                grid.append(row)
        if not grid:
            return grid
        width = max(len(r) for r in grid)
        return [r + [""] * (width - len(r)) for r in grid]


class XlsxParser:
    """Excel .xlsx: the first worksheet as a table (shared strings resolved)."""

    name = "xlsx"
    content_types: tuple[str, ...] = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    def supports(self, content_type: str) -> bool:
        return content_type in self.content_types

    def parse(self, raw: RawSource) -> IntermediateRepresentation:
        with _open_zip(raw) as zf:
            shared = self._shared_strings(zf)
            sheets = sorted(
                n for n in zf.namelist()
                if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")
            )
            if not sheets:
                raise ParserError(raw.source_id, "no worksheets in xlsx")
            payloads = [(n, zf.read(n)) for n in sheets]

        elements: list[IRElement] = []
        for idx, (_, xml) in enumerate(payloads):
            grid = self._sheet_grid(xml, shared)
            if grid:
                elements.append(_table_element(raw, grid, idx, f"xlsx sheet {idx}"))
        return _finish(raw, elements, "xlsx")

    @staticmethod
    def _shared_strings(zf: zipfile.ZipFile) -> list[str]:
        try:
            xml = zf.read("xl/sharedStrings.xml")
        except KeyError:
            return []
        root = ET.fromstring(xml)  # noqa: S314 - local trusted office file
        out: list[str] = []
        for si in root:
            out.append(" ".join(t.text or "" for t in si.iter() if _local(t.tag) == "t"))
        return out

    def _sheet_grid(self, xml: bytes, shared: list[str]) -> list[list[str]]:
        root = ET.fromstring(xml)  # noqa: S314 - local trusted office file
        rows: list[list[str]] = []
        for row in root.iter():
            if _local(row.tag) != "row":
                continue
            cells: list[str] = []
            for c in row:
                if _local(c.tag) != "c":
                    continue
                cells.append(self._cell_value(c, shared))
            if any(v != "" for v in cells):
                rows.append(cells)
        if not rows:
            return rows
        width = max(len(r) for r in rows)
        return [r + [""] * (width - len(r)) for r in rows]

    @staticmethod
    def _cell_value(c: ET.Element, shared: list[str]) -> str:
        cell_type = c.attrib.get("t")
        v = next((e for e in c if _local(e.tag) == "v"), None)
        inline = next((e for e in c if _local(e.tag) == "is"), None)
        if cell_type == "s" and v is not None and v.text is not None:
            try:
                return shared[int(v.text)]
            except (ValueError, IndexError):
                return ""
        if cell_type == "inlineStr" and inline is not None:
            return _text_of(inline)
        return v.text if v is not None and v.text is not None else ""


class OdtParser:
    """OpenDocument text .odt: text + tables from content.xml."""

    name = "odt"
    content_types: tuple[str, ...] = ("application/vnd.oasis.opendocument.text",)

    def supports(self, content_type: str) -> bool:
        return content_type in self.content_types

    def parse(self, raw: RawSource) -> IntermediateRepresentation:
        with _open_zip(raw) as zf:
            try:
                xml = zf.read("content.xml")
            except KeyError as exc:
                raise ParserError(raw.source_id, "missing content.xml") from exc
        root = ET.fromstring(xml)  # noqa: S314 - local trusted office file

        elements: list[IRElement] = []
        t_index = 0
        for el in root.iter():
            name = _local(el.tag)
            if name == "table":
                grid = self._table_grid(el)
                if grid:
                    elements.append(_table_element(raw, grid, t_index, "odt table"))
                    t_index += 1
            elif name in ("h", "p"):
                text = _text_of(el)
                if text:
                    elements.append(_text_element(raw, text, heading=(name == "h")))
        return _finish(raw, elements, "odt")

    @staticmethod
    def _table_grid(table: ET.Element) -> list[list[str]]:
        grid: list[list[str]] = []
        for tr in table.iter():
            if _local(tr.tag) != "table-row":
                continue
            row = [_text_of(tc) for tc in tr if _local(tc.tag) == "table-cell"]
            if row:
                grid.append(row)
        if not grid:
            return grid
        width = max(len(r) for r in grid)
        return [r + [""] * (width - len(r)) for r in grid]


class EpubParser:
    """EPUB: concatenated XHTML content documents (text + tables)."""

    name = "epub"
    content_types: tuple[str, ...] = ("application/epub+zip",)

    def supports(self, content_type: str) -> bool:
        return content_type in self.content_types

    def parse(self, raw: RawSource) -> IntermediateRepresentation:
        from locus_engine.parsers.html import _Collector

        with _open_zip(raw) as zf:
            docs = sorted(
                n for n in zf.namelist()
                if n.lower().endswith((".xhtml", ".html", ".htm"))
            )
            payloads = [zf.read(n) for n in docs]

        elements: list[IRElement] = []
        t_index = 0
        for data in payloads:
            collector = _Collector()
            collector.feed(data.decode("utf-8", errors="replace"))
            for block in collector.text_blocks:
                elements.append(_text_element(raw, block))
            for grid in collector.tables:
                if grid:
                    elements.append(_table_element(raw, grid, t_index, "epub table"))
                    t_index += 1
        return _finish(raw, elements, "epub")
