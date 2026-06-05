"""Plain-text parser (dependency-free).

Splits a text file into located paragraph elements on blank lines. This does not
fabricate tabular structure; it makes the content available to the engine so the
universal "document elements" fallback (in the extractor) can present it as a table,
and so grounding has source text to score against.

Requirements: 2.2, 3.1, 3.3.
"""

from __future__ import annotations

from locus_engine.errors import ParserError
from locus_engine.ir import (
    IntermediateRepresentation,
    IRElement,
    IRElementKind,
)
from locus_engine.plugins import RawSource
from locus_engine.provenance import CharSpan, SourceLocation


class TextParser:
    """Parses plain text into paragraph elements split on blank lines."""

    name = "text"
    content_types: tuple[str, ...] = ("text/plain",)

    def supports(self, content_type: str) -> bool:
        return content_type in self.content_types

    def parse(self, raw: RawSource) -> IntermediateRepresentation:
        if raw.data is None:
            raise ParserError(raw.source_id, "text parser requires raw bytes")
        try:
            text = raw.data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ParserError(raw.source_id, f"decode failed: {exc}") from exc

        elements: list[IRElement] = []
        offset = 0
        for block in text.split("\n\n"):
            stripped = block.strip()
            if stripped:
                loc = SourceLocation(
                    source_id=raw.source_id,
                    index=0,
                    char_span=CharSpan(start=offset, end=offset + len(block)),
                    note="text block",
                )
                elements.append(
                    IRElement(kind=IRElementKind.PARAGRAPH, text=stripped, location=loc)
                )
            offset += len(block) + 2

        if not elements:
            raise ParserError(raw.source_id, "no text content")
        return IntermediateRepresentation(
            source_id=raw.source_id, content_type=raw.content_type, elements=elements
        )
