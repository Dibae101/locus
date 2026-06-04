"""Tests for the PDF parser and a full PDF pipeline run.

Skips gracefully if the optional 'pdf' extra (pdfplumber) is not installed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pdfplumber")

from locus_engine.ir import IRElementKind  # noqa: E402
from locus_engine.parsers.pdf import PdfParser  # noqa: E402
from locus_engine.plugins import RawSource  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample.pdf"


def _raw() -> RawSource:
    return RawSource(
        source_id="sample.pdf",
        content_type="application/pdf",
        data=SAMPLE.read_bytes(),
    )


def test_pdf_parser_extracts_text_with_page_provenance() -> None:
    ir = PdfParser().parse(_raw())
    paragraphs = [e for e in ir.elements if e.kind is IRElementKind.PARAGRAPH]
    assert paragraphs, "expected at least one text block"
    text = paragraphs[0].text
    assert "INV-2001" in text
    assert "Acme Corp" in text
    # page provenance with bounding box
    loc = paragraphs[0].location
    assert loc.index == 0
    assert loc.bbox is not None and loc.bbox.x1 > 0


def test_pdf_parser_produces_located_text() -> None:
    ir = PdfParser().parse(_raw())
    src_text = "\n".join(e.text for e in ir.elements if e.text)
    assert "512.75" in src_text
    assert all(e.location.source_id == "sample.pdf" for e in ir.elements)
