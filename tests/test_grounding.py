"""Tests for degraded-mode grounding (Stage 3.4)."""

from __future__ import annotations

from locus_engine.ir import (
    IntermediateRepresentation,
    IRElement,
    IRElementKind,
)
from locus_engine.provenance import GroundingMode, Provenance, SourceLocation
from locus_engine.table import Cell, ProvenancedTable, Row
from locus_engine.validate.grounding import GroundingValidator, SimilarityScorer


def test_scorer_supported_vs_unsupported() -> None:
    s = SimilarityScorer()
    assert s.score("Acme Corp", "the vendor is Acme Corp on this invoice") > 0.8
    assert s.score("Zzzz Unrelated", "the vendor is Acme Corp") < 0.5


def _ir_with_text(text: str) -> IntermediateRepresentation:
    loc = SourceLocation(source_id="s1", index=0)
    el = IRElement(kind=IRElementKind.PARAGRAPH, text=text, location=loc)
    return IntermediateRepresentation(source_id="s1", content_type="text/plain", elements=[el])


def _table(value: str) -> ProvenancedTable:
    loc = SourceLocation(source_id="s1", index=0)
    cell = Cell(column="vendor", value=value, provenance=Provenance(locations=[loc]))
    return ProvenancedTable(columns=["vendor"], rows=[Row(cells={"vendor": cell})])


def test_supported_cell_scored_high_not_flagged() -> None:
    ir = _ir_with_text("Vendor: Acme Corp, total 250")
    table = GroundingValidator().validate(_table("Acme Corp"), ir, threshold=0.7)
    cell = table.rows[0].cells["vendor"]
    assert cell.provenance.faithfulness is not None and cell.provenance.faithfulness >= 0.7
    assert cell.provenance.grounding_mode is GroundingMode.DEGRADED
    assert table.rows[0].flagged is False


def test_unsupported_cell_flagged() -> None:
    ir = _ir_with_text("Vendor: Acme Corp, total 250")
    table = GroundingValidator().validate(_table("Totally Different Inc"), ir, threshold=0.7)
    assert table.rows[0].flagged is True


def test_reject_mode_excludes_flagged_rows() -> None:
    ir = _ir_with_text("Vendor: Acme Corp")
    table = GroundingValidator().validate(
        _table("Totally Different Inc"), ir, threshold=0.7, rejection_mode="reject"
    )
    assert table.rows == []
