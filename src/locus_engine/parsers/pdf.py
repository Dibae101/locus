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
from typing import Any

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
                "PDF parsing requires the 'pdf' extra: pip install 'locus-etl[pdf]'",
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

        # Reconstruct readable paragraphs from positioned words. extract_text() drops
        # inter-word spaces and reads straight across multi-column layouts; rebuilding
        # from words preserves spacing, respects columns, and splits real paragraphs.
        paragraphs = self._paragraphs_from_words(page)
        for text, para_words in paragraphs:
            produced_text = True
            elements.append(
                IRElement(
                    kind=IRElementKind.PARAGRAPH,
                    text=text,
                    location=SourceLocation(
                        source_id=source_id,
                        index=page_index,
                        bbox=self._para_bbox(page_index, para_words),
                    ),
                )
            )
        return produced_text or bool(tables)

    @staticmethod
    def _para_bbox(page_index: int, words: list[dict[str, Any]]) -> BBox | None:
        """A bounding box enclosing all words in a paragraph (origin top-left)."""
        if not words:
            return None
        return BBox(
            page=page_index,
            x0=min(w["x0"] for w in words),
            y0=min(w["top"] for w in words),
            x1=max(w["x1"] for w in words),
            y1=max(w["bottom"] for w in words),
        )

    def _paragraphs_from_words(self, page: object) -> list[tuple[str, list[dict[str, Any]]]]:
        """Group a page's positioned words into reading-ordered paragraphs.

        Steps: detect columns by a vertical whitespace gutter, then within each column
        group words into lines (shared baseline) and lines into paragraphs (split on a
        larger-than-normal vertical gap). Words on a line are joined with single
        spaces, fixing the dropped-space problem of ``extract_text()``. Each paragraph
        is returned with the words it contains so callers can compute a bounding box.
        """
        x_tol = self._word_tolerance(page)
        try:
            words = page.extract_words(  # type: ignore[attr-defined]
                use_text_flow=False, x_tolerance=x_tol
            )
        except Exception:  # pragma: no cover - defensive
            words = []
        if not words:
            text = page.extract_text() or ""  # type: ignore[attr-defined]
            stripped = text.strip()
            return [(stripped, [])] if stripped else []

        page_width = float(getattr(page, "width", 0.0) or 0.0)
        flows = self._reading_flows(words, page_width)

        paragraphs: list[tuple[str, list[dict[str, Any]]]] = []
        for flow in flows:
            paragraphs.extend(self._column_paragraphs(flow))
        return paragraphs

    @staticmethod
    def _word_tolerance(page: object) -> float:
        """Derive the horizontal word-split tolerance from the page's font size.

        Some PDFs encode no space characters and separate words only by small
        positional gaps narrower than pdfplumber's default ``x_tolerance`` (3.0),
        which silently fuses words (``CloudPlatformandDevOps``). Scaling the tolerance
        to the common glyph height (~0.18x) recovers word boundaries without
        over-splitting normal text.
        """
        try:
            heights = [round(c["height"], 1) for c in page.chars if c.get("height")]  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive
            heights = []
        if not heights:
            return 1.5
        common = max(set(heights), key=heights.count)
        return float(max(1.0, min(3.0, common * 0.18)))

    def _reading_flows(
        self, words: list[dict[str, Any]], page_width: float
    ) -> list[list[dict[str, Any]]]:
        """Return word groups in human reading order, handling mixed layouts.

        Academic papers commonly place a full-width title/abstract header above a
        two-column body. Reading straight across zippers the two body columns together
        and cuts sentences in half. This method finds a vertical *gutter* — an x
        position no word crosses — near the page middle, then classifies each line as
        spanning the gutter (full-width title) or living in the left/right column, and
        segments the page so a two-column region emits its whole left column before its
        right column. Single-column pages (no persistent gutter) read top-to-bottom.
        """
        if page_width <= 0 or len(words) < 60:
            return [words]

        gutter = self._find_gutter(words, page_width)
        if gutter is None:
            return [words]

        lines = self._group_lines(words)
        # Classify each line relative to the gutter.
        classified: list[tuple[str, list[dict[str, Any]], list[dict[str, Any]]]] = []
        for ln in lines:
            crosses = any(w["x0"] < gutter < w["x1"] for w in ln["words"])
            lwords = [w for w in ln["words"] if w["x1"] <= gutter]
            rwords = [w for w in ln["words"] if w["x0"] >= gutter]
            if crosses or not (lwords and rwords):
                # A word straddles the gutter (full-width line) or the line sits in a
                # single column only.
                kind = "span" if crosses else ("left" if lwords else "right")
            else:
                kind = "split"
            classified.append((kind, lwords, rwords))

        return self._segment_flows(classified)

    @staticmethod
    def _find_gutter(words: list[dict[str, Any]], page_width: float) -> float | None:
        """Find a vertical whitespace channel near mid-page that no word crosses.

        Scans candidate x positions in the central third of the page and returns the
        one crossed by the fewest words (must be near-zero), provided both sides carry
        substantial text. Returns None for single-column layouts.
        """
        mid = page_width / 2.0
        lo, hi = int(page_width * 0.35), int(page_width * 0.65)
        best_x: float | None = None
        best_cross = None
        for x in range(lo, hi + 1, 4):
            crossing = sum(1 for w in words if w["x0"] < x < w["x1"])
            left = sum(1 for w in words if w["x1"] <= x)
            right = sum(1 for w in words if w["x0"] >= x)
            # Need an essentially empty channel and balanced, substantial sides.
            if (
                crossing <= 0.01 * len(words)
                and left >= 0.25 * len(words)
                and right >= 0.25 * len(words)
            ):
                # Prefer the emptiest channel closest to the true middle.
                score = (crossing, abs(x - mid))
                if best_cross is None or score < best_cross:
                    best_cross = score
                    best_x = float(x)
        return best_x

    @staticmethod
    def _segment_flows(
        classified: list[tuple[str, list[dict[str, Any]], list[dict[str, Any]]]],
    ) -> list[list[dict[str, Any]]]:
        """Walk classified lines top-to-bottom, emitting full-width spans in place and
        grouping consecutive two-column runs so each whole left column precedes its
        right column."""
        flows: list[list[dict[str, Any]]] = []
        i = 0
        n = len(classified)
        while i < n:
            kind = classified[i][0]
            if kind == "span":
                block: list[dict[str, Any]] = []
                while i < n and classified[i][0] == "span":
                    _, lw, rw = classified[i]
                    block.extend(lw + rw)
                    i += 1
                if block:
                    flows.append(block)
            else:
                left: list[dict[str, Any]] = []
                right: list[dict[str, Any]] = []
                while i < n and classified[i][0] in ("split", "left", "right"):
                    _, lw, rw = classified[i]
                    left.extend(lw)
                    right.extend(rw)
                    i += 1
                if left:
                    flows.append(left)
                if right:
                    flows.append(right)
        return flows

    def _column_paragraphs(
        self, words: list[dict[str, Any]]
    ) -> list[tuple[str, list[dict[str, Any]]]]:
        lines = self._group_lines(words)
        if not lines:
            return []
        # Estimate the typical line height to choose a paragraph-break threshold.
        tops = [ln["top"] for ln in lines]
        gaps = [b - a for a, b in zip(tops, tops[1:], strict=False)]
        heights = [ln["height"] for ln in lines if ln["height"] > 0]
        typical = (sum(heights) / len(heights)) if heights else 12.0
        break_gap = typical * 1.8

        paragraphs: list[tuple[str, list[dict[str, Any]]]] = []
        cur_text: list[str] = []
        cur_words: list[dict[str, Any]] = []
        for i, ln in enumerate(lines):
            if i > 0 and gaps[i - 1] > break_gap and cur_text:
                paragraphs.append((" ".join(cur_text).strip(), cur_words))
                cur_text, cur_words = [], []
            cur_text.append(ln["text"])
            cur_words.extend(ln["words"])
        if cur_text:
            paragraphs.append((" ".join(cur_text).strip(), cur_words))
        return [(t, w) for t, w in paragraphs if t]

    @staticmethod
    def _group_lines(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Group words into lines by shared vertical position, ordered top-to-bottom
        then left-to-right. Returns dicts with joined text, top, and height."""
        ordered = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))
        lines: list[dict[str, Any]] = []
        for w in ordered:
            placed = False
            for ln in lines:
                # Same line if vertical centers overlap within half a line height.
                if abs(w["top"] - ln["top"]) <= max(3.0, 0.5 * ln["height"]):
                    ln["words"].append(w)
                    ln["height"] = max(ln["height"], w["bottom"] - w["top"])
                    placed = True
                    break
            if not placed:
                lines.append(
                    {"top": w["top"], "height": w["bottom"] - w["top"], "words": [w]}
                )
        lines.sort(key=lambda ln: ln["top"])
        for ln in lines:
            ln["words"].sort(key=lambda w: w["x0"])
            ln["text"] = " ".join(w["text"] for w in ln["words"])
        return lines
