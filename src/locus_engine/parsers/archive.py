"""ZIP archive parser (dependency-free).

Expands a ``.zip`` archive and parses each contained file that a sibling parser
understands (CSV, JSON, Markdown, HTML, text, and the Office/OpenDocument formats),
merging all extracted elements into one IR. Each element keeps a ``SourceLocation``
whose ``note`` records the member path, so provenance points at the file inside the
archive. Binary members with no parser are skipped.

Requirements: 2.2, 3.1, 3.2, 3.3.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from locus_engine.connectors.files import detect_content_type
from locus_engine.errors import ParserError
from locus_engine.ir import IntermediateRepresentation, IRElement
from locus_engine.plugins import Parser, RawSource


class ArchiveParser:
    """Parses the contents of a ZIP archive by delegating to per-format parsers."""

    name = "archive"
    content_types: tuple[str, ...] = ("application/zip",)

    def supports(self, content_type: str) -> bool:
        return content_type in self.content_types

    def parse(self, raw: RawSource) -> IntermediateRepresentation:
        if raw.data is None:
            raise ParserError(raw.source_id, "archive parser requires raw bytes")
        try:
            zf = zipfile.ZipFile(io.BytesIO(raw.data))
        except zipfile.BadZipFile as exc:
            raise ParserError(raw.source_id, f"not a valid zip: {exc}") from exc

        parsers = self._member_parsers()
        elements: list[IRElement] = []
        with zf:
            for member in zf.namelist():
                if member.endswith("/"):
                    continue
                content_type = detect_content_type(Path(member))
                parser = parsers.get(content_type)
                if parser is None:
                    continue
                try:
                    data = zf.read(member)
                except KeyError:  # pragma: no cover - defensive
                    continue
                member_id = f"{raw.source_id}!{member}"
                member_raw = RawSource(
                    source_id=member_id, content_type=content_type, data=data
                )
                try:
                    member_ir = parser.parse(member_raw)
                except ParserError:
                    continue
                for el in member_ir.elements:
                    el.location.note = f"{member}: {el.location.note or ''}".strip().rstrip(":")
                    elements.append(el)

        if not elements:
            raise ParserError(
                raw.source_id, "no parseable files found inside the archive"
            )
        return IntermediateRepresentation(
            source_id=raw.source_id, content_type=raw.content_type, elements=elements
        )

    @staticmethod
    def _member_parsers() -> dict[str, Parser]:
        """Map content type -> parser instance for archive members. Avoids recursing
        into nested archives to keep extraction bounded."""
        from locus_engine.parsers.csv_parser import CsvParser
        from locus_engine.parsers.html import HtmlParser
        from locus_engine.parsers.json_parser import JsonParser
        from locus_engine.parsers.markdown import MarkdownParser
        from locus_engine.parsers.office import (
            DocxParser,
            EpubParser,
            OdtParser,
            PptxParser,
            XlsxParser,
        )
        from locus_engine.parsers.text import TextParser

        instances: list[Parser] = [
            CsvParser(),
            HtmlParser(),
            JsonParser(),
            MarkdownParser(),
            TextParser(),
            DocxParser(),
            PptxParser(),
            XlsxParser(),
            OdtParser(),
            EpubParser(),
        ]
        mapping: dict[str, Parser] = {}
        for inst in instances:
            for ct in inst.content_types:
                mapping.setdefault(ct, inst)
        return mapping
