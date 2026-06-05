"""Markdown parser (dependency-free).

Extracts GitHub-flavored pipe tables and text blocks from Markdown. Pipe tables
become IR tables (header + rows); headings and paragraphs become located text
elements. Runs locally with no LLM and no network, so it lives in the deterministic
engine.

Requirements: 2.2, 3.1, 3.2, 3.3.
"""

from __future__ import annotations

import re

from locus_engine.errors import ParserError
from locus_engine.ir import (
    IntermediateRepresentation,
    IRElement,
    IRElementKind,
    IRTable,
)
from locus_engine.plugins import RawSource
from locus_engine.provenance import SourceLocation

# A markdown table separator row, e.g. ``|---|:--:|---:|``.
_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")


class MarkdownParser:
    """Parses Markdown into IR tables (pipe tables) and located text blocks."""

    name = "markdown"
    content_types: tuple[str, ...] = ("text/markdown", "text/x-markdown")

    def supports(self, content_type: str) -> bool:
        return content_type in self.content_types

    def parse(self, raw: RawSource) -> IntermediateRepresentation:
        if raw.data is None:
            raise ParserError(raw.source_id, "markdown parser requires raw bytes")
        try:
            text = raw.data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ParserError(raw.source_id, f"decode failed: {exc}") from exc

        lines = text.splitlines()
        elements: list[IRElement] = []
        table_index = 0
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i]
            # Detect a pipe table: a header row, a separator row, then >=0 body rows.
            if (
                "|" in line
                and i + 1 < n
                and _SEP_RE.match(lines[i + 1])
                and "|" in lines[i + 1]
            ):
                grid, consumed = self._consume_table(lines, i)
                if grid:
                    loc = SourceLocation(
                        source_id=raw.source_id,
                        index=table_index,
                        note=f"markdown table {table_index}",
                    )
                    elements.append(
                        IRElement(
                            kind=IRElementKind.TABLE,
                            table=IRTable(cells=grid, location=loc),
                            location=loc,
                        )
                    )
                    table_index += 1
                    i += consumed
                    continue

            stripped = line.strip()
            if stripped:
                kind = (
                    IRElementKind.HEADING
                    if stripped.startswith("#")
                    else IRElementKind.PARAGRAPH
                )
                loc = SourceLocation(source_id=raw.source_id, index=0, note="markdown text")
                elements.append(
                    IRElement(kind=kind, text=stripped.lstrip("# ").strip(), location=loc)
                )
            i += 1

        if not elements:
            raise ParserError(raw.source_id, "no content extracted from markdown")
        return IntermediateRepresentation(
            source_id=raw.source_id, content_type=raw.content_type, elements=elements
        )

    def _consume_table(self, lines: list[str], start: int) -> tuple[list[list[str]], int]:
        """Read a pipe table starting at the header line. Returns (grid, lines_used)."""
        header = self._split_row(lines[start])
        grid = [header]
        i = start + 2  # skip header + separator
        while i < len(lines) and "|" in lines[i] and lines[i].strip():
            grid.append(self._normalize_row(self._split_row(lines[i]), len(header)))
            i += 1
        return grid, i - start

    @staticmethod
    def _split_row(line: str) -> list[str]:
        s = line.strip()
        if s.startswith("|"):
            s = s[1:]
        if s.endswith("|"):
            s = s[:-1]
        # Split on unescaped pipes, then unescape and strip markdown emphasis markers.
        cells = re.split(r"(?<!\\)\|", s)
        return [c.replace("\\|", "|").strip().strip("*").strip() for c in cells]

    @staticmethod
    def _normalize_row(cells: list[str], width: int) -> list[str]:
        if len(cells) < width:
            cells = cells + [""] * (width - len(cells))
        elif len(cells) > width:
            cells = cells[:width]
        return cells
