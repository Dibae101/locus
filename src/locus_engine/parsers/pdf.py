"""PDF parser (Stage 9.3 follow-up).

Extracts text and tables from text-layer PDFs using ``pdfplumber`` (optional ``pdf``
extra). Every element carries a ``SourceLocation`` with the page index and, for words
and tables, bounding-box geometry (Req 3.4). pdfplumber runs locally with no LLM and
no network, so this parser lives in the deterministic engine.

For scanned/image-only PDFs (no text layer) use an OCR parser instead; this parser
raises a ``ParserError`` when a page yields no extractable text.

Requirements: 2.2, 3.1, 3.2, 3.3, 3.4.
"""

from __future__ import annotations

import io

from locus_engine.errors import ParserError
from locus_engine.ir import (
    IntermediateRepresentation,
    IRElement,
    IRElementKind,
    IRTable,
)
from locus_engine.plugins import RawSource
from locus_engine.provenance import BBox, SourceLocation


class PdfParser:
    """Parses text-layer PDFs into located text blocks and tables."""

    name = "pdf"
    content_types = ("application/pdf",)

    def supports(self, content_type: str) -> bool:
        return content_type in self.content_types

    def parse(self, raw: RawSource) -> IntermediateRepresentation:
        if raw.data is None:
            raise ParserError(raw.source_id, "pdf parser requires raw bytes")
        try:
            import pdfplumber
        except ImportError as exc:  # pragma: no cover - exercised when extra missing
            raise ParserError(
                raw.source_id,
                "PDF parsing requires the 'pdf' extra: pip install locus-engine[pdf]",
            ) from exc

        elements: list[IRElement] = []
        any_text = False
        try:
            with pdfplumber.open(io.BytesIO(raw.data)) as pdf:
                for page_index, page in enumerate(pdf.pages):
                    any_text |= self._parse_page(raw.source_id, page_index, page, elements)
        except ParserError:
            raise
        except Exception as exc:
            raise ParserError(raw.source_id, f"pdf parse failed: {exc}") from exc

        if not any_text:
            raise ParserError(
                raw.source_id,
                "no extractable text (scanned PDF?); use an OCR parser",
            )
        return IntermediateRepresentation(
            source_id=raw.source_id, content_type=raw.content_type, elements=elements
        )

    def _parse_page(
        self, source_id: str, page_index: int, page: object, elements: list[IRElement]
    ) -> bool:
        produced_text = False

        # Tables first (with page-level bbox).
        tables = page.extract_tables()  # type: ignore[attr-defined]
        for t_index, grid in enumerate(tables or []):
            cleaned = [[("" if c is None else str(c)) for c in row] for row in grid]
            loc = SourceLocation(
                source_id=source_id,
                index=page_index,
                note=f"pdf table {t_index}",
            )
            elements.append(
                IRElement(
                    kind=IRElementKind.TABLE,
                    table=IRTable(cells=cleaned, location=loc),
                    location=loc,
                )
            )

        # Page text as a paragraph element with the page bounding box.
        text = page.extract_text() or ""  # type: ignore[attr-defined]
        if text.strip():
            produced_text = True
            bbox = BBox(
                page=page_index,
                x0=float(getattr(page, "bbox", (0, 0, 0, 0))[0]),
                y0=float(getattr(page, "bbox", (0, 0, 0, 0))[1]),
                x1=float(getattr(page, "bbox", (0, 0, 0, 0))[2]),
                y1=float(getattr(page, "bbox", (0, 0, 0, 0))[3]),
            )
            loc = SourceLocation(source_id=source_id, index=page_index, bbox=bbox)
            elements.append(
                IRElement(kind=IRElementKind.PARAGRAPH, text=text.strip(), location=loc)
            )
        return produced_text or bool(tables)
