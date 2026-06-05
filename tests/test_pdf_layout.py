"""Tests for the PDF parser's text-layout reconstruction logic.

These exercise the column / line / paragraph grouping on synthetic word boxes (the
same dict shape pdfplumber's ``extract_words`` returns), so they need no real PDF and
no third-party PDF writer. They lock in the fixes for:
  - dropped inter-word spaces (words joined with single spaces),
  - whole-page-as-one-paragraph (vertical gaps split paragraphs),
  - two-column scrambling (genuine gutter splits columns; single-column left intact).
"""

from __future__ import annotations

from locus_engine.parsers.pdf import PdfParser


def _word(text: str, top: float, x0: float, *, height: float = 10.0, char_w: float = 6.0) -> dict:
    return {
        "text": text,
        "x0": x0,
        "x1": x0 + char_w * len(text),
        "top": top,
        "bottom": top + height,
    }


def _line_of(words: list[str], top: float, x_start: float = 50.0) -> list[dict]:
    out: list[dict] = []
    x = x_start
    for tok in words:
        w = _word(tok, top, x)
        out.append(w)
        x = w["x1"] + 6.0  # inter-word gap
    return out


def test_words_joined_with_spaces_in_reading_order() -> None:
    parser = PdfParser()
    words = _line_of(["Cloud", "Platform", "and", "DevOps"], top=100.0)
    lines = parser._group_lines(words)
    assert len(lines) == 1
    assert lines[0]["text"] == "Cloud Platform and DevOps"


def test_paragraph_break_on_vertical_gap() -> None:
    parser = PdfParser()
    # Two blocks separated by a large vertical gap -> two paragraphs.
    block1 = _line_of(["first", "para", "line", "one"], top=100.0)
    block1 += _line_of(["still", "first", "para"], top=112.0)
    block2 = _line_of(["second", "para", "here"], top=160.0)  # big gap
    paras = [text for text, _words in parser._column_paragraphs(block1 + block2)]
    assert len(paras) == 2
    assert paras[0].startswith("first para line one")
    assert paras[1] == "second para here"


def test_single_column_resume_not_split() -> None:
    parser = PdfParser()
    # Full-width header + indented bullets crossing the midline => single column.
    words: list[dict] = []
    words += _line_of(["Alex", "Morgan", "Carter"], top=20.0, x_start=240.0)  # centered
    for i in range(20):
        words += _line_of(["bullet", "text", "spanning", "the", "page", "width"],
                          top=40.0 + i * 12, x_start=50.0)
    columns = parser._split_columns(words, page_width=612.0)
    assert len(columns) == 1


def test_two_column_paper_is_split() -> None:
    parser = PdfParser()
    # Clear left and right blocks with an empty central gutter => two columns.
    # Left column ~50-200, right column ~340-490, gutter ~290-322 (band) empty.
    words: list[dict] = []
    for i in range(30):
        words += _line_of(["left", "col", "word"], top=40.0 + i * 12, x_start=50.0)
        words += _line_of(["right", "col", "word"], top=40.0 + i * 12, x_start=340.0)
    columns = parser._split_columns(words, page_width=612.0)
    assert len(columns) == 2
    left, right = columns
    assert all(w["x1"] <= 306.0 for w in left)
    assert all(w["x0"] >= 306.0 for w in right)


def test_word_tolerance_scales_with_font_height() -> None:
    parser = PdfParser()

    class _FakePage:
        chars = [{"height": 10.0}] * 50

    tol = parser._word_tolerance(_FakePage())
    assert 1.0 <= tol <= 3.0
    # 10pt * 0.18 = 1.8
    assert abs(tol - 1.8) < 0.01
