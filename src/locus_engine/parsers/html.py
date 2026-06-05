"""HTML parser (Stage 9.2).

Extracts text and tables from HTML. Uses the standard-library ``html.parser`` so the
core stays dependency-free; richer main-content extraction (trafilatura) and a fast
DOM (selectolax) are optional upgrades a plugin can swap in. Char offsets are attached
as ``SourceLocation`` provenance.

Requirements: 2.2, 3.1, 3.2, 3.3.
"""

from __future__ import annotations

from html.parser import HTMLParser

from locus_engine.errors import ParserError
from locus_engine.ir import (
    IntermediateRepresentation,
    IRElement,
    IRElementKind,
    IRTable,
)
from locus_engine.plugins import RawSource
from locus_engine.provenance import CharSpan, SourceLocation

_BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li"}
_SKIP_TAGS = {"script", "style"}


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text_blocks: list[str] = []
        self.tables: list[list[list[str]]] = []
        self._skip = False
        self._buf: list[str] = []
        self._in_table = False
        self._cur_table: list[list[str]] = []
        self._cur_row: list[str] = []
        self._cell_buf: list[str] = []
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in _SKIP_TAGS:
            self._skip = True
        elif tag == "table":
            self._in_table = True
            self._cur_table = []
        elif tag == "tr" and self._in_table:
            self._cur_row = []
        elif tag in ("td", "th") and self._in_table:
            self._in_cell = True
            self._cell_buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip = False
        elif tag == "table" and self._in_table:
            if self._cur_table:
                self.tables.append(self._cur_table)
            self._in_table = False
        elif tag == "tr" and self._in_table:
            if self._cur_row:
                self._cur_table.append(self._cur_row)
        elif tag in ("td", "th") and self._in_table:
            self._cur_row.append("".join(self._cell_buf).strip())
            self._in_cell = False
        elif tag in _BLOCK_TAGS:
            text = "".join(self._buf).strip()
            if text:
                self.text_blocks.append(text)
            self._buf = []

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_cell:
            self._cell_buf.append(data)
        else:
            self._buf.append(data)


class HtmlParser:
    """Parses HTML into located text blocks and tables (stdlib-based)."""

    name = "html"
    content_types: tuple[str, ...] = ("text/html",)

    def supports(self, content_type: str) -> bool:
        return content_type in self.content_types

    def parse(self, raw: RawSource) -> IntermediateRepresentation:
        if raw.data is None:
            raise ParserError(raw.source_id, "html parser requires raw bytes")
        try:
            text = raw.data.decode("utf-8", errors="replace")
        except Exception as exc:  # pragma: no cover - decode is lenient
            raise ParserError(raw.source_id, f"decode failed: {exc}") from exc

        collector = _Collector()
        collector.feed(text)

        elements: list[IRElement] = []
        offset = 0
        for block in collector.text_blocks:
            loc = SourceLocation(
                source_id=raw.source_id,
                index=0,
                char_span=CharSpan(start=offset, end=offset + len(block)),
            )
            elements.append(IRElement(kind=IRElementKind.PARAGRAPH, text=block, location=loc))
            offset += len(block)

        for t_idx, grid in enumerate(collector.tables):
            loc = SourceLocation(source_id=raw.source_id, index=t_idx, note="html table")
            elements.append(
                IRElement(
                    kind=IRElementKind.TABLE,
                    table=IRTable(cells=grid, location=loc),
                    location=loc,
                )
            )

        if not elements:
            raise ParserError(raw.source_id, "no content extracted from html")
        return IntermediateRepresentation(
            source_id=raw.source_id, content_type=raw.content_type, elements=elements
        )
