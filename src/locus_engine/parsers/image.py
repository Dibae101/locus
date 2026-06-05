"""Image parser — clear guidance toward OCR.

Image files (PNG/JPEG/…) carry no text layer, so deterministic parsing cannot read
them. Rather than failing with a generic "no parser" message, this parser raises an
actionable error pointing at the OCR extra. Wiring a real OCR engine (rapidocr) is a
follow-up; this keeps the failure mode honest and informative.

Requirements: 2.2, 2.6.
"""

from __future__ import annotations

from locus_engine.errors import ParserError
from locus_engine.ir import IntermediateRepresentation
from locus_engine.plugins import RawSource


class ImageParser:
    """Routes image content types to a clear OCR-required error."""

    name = "image"
    content_types = (
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/tiff",
        "image/bmp",
        "image/webp",
    )

    def supports(self, content_type: str) -> bool:
        return content_type in self.content_types

    def parse(self, raw: RawSource) -> IntermediateRepresentation:
        raise ParserError(
            raw.source_id,
            "image files have no text layer; OCR is required to read them. Install the "
            "OCR extra (pip install 'locus-etl[ocr]') — OCR extraction is on the "
            "roadmap and not yet wired.",
        )
