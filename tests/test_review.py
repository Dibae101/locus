"""Tests for the human-in-the-loop review API (Stage 8)."""

from __future__ import annotations

from locus_engine.provenance import OpKind, Provenance, SourceLocation
from locus_engine.review import ReviewQueue, corrections_as_prompt_context
from locus_engine.table import Cell, Row


def _flagged_row() -> Row:
    cell = Cell(
        column="vendor",
        value="Acme Crop",  # typo to be corrected
        provenance=Provenance(locations=[SourceLocation(source_id="doc-1", index=0)]),
    )
    return Row(cells={"vendor": cell}, flagged=True, source_id="doc-1")


def test_flagged_row_enters_queue() -> None:
    q = ReviewQueue()
    row = _flagged_row()
    q.add_flagged(row)
    assert len(q.pending) == 1


def test_unflagged_row_not_queued() -> None:
    q = ReviewQueue()
    row = _flagged_row()
    row.flagged = False
    q.add_flagged(row)
    assert q.pending == []


def test_correction_updates_cell_and_records_feedback() -> None:
    q = ReviewQueue()
    row = _flagged_row()
    q.add_flagged(row)
    new_cell = q.correct(row.row_id, "vendor", "Acme Corp", reviewer="alice")

    assert new_cell.value == "Acme Corp"
    assert new_cell.provenance.lineage[-1].op is OpKind.REVIEW
    # provenance preserved
    assert new_cell.provenance.locations[0].source_id == "doc-1"
    # feedback recorded
    assert len(q.feedback) == 1
    fb = q.feedback[0]
    assert fb.original_value == "Acme Crop"
    assert fb.corrected_value == "Acme Corp"
    assert fb.reviewer == "alice"
    assert fb.timestamp


def test_approve_includes_row_without_revalidation() -> None:
    q = ReviewQueue()
    row = _flagged_row()
    q.add_flagged(row)
    approved = q.approve(row.row_id)
    assert approved.flagged is False
    assert q.pending == []


def test_corrections_prompt_context() -> None:
    q = ReviewQueue()
    row = _flagged_row()
    q.add_flagged(row)
    q.correct(row.row_id, "vendor", "Acme Corp", reviewer="alice")
    ctx = corrections_as_prompt_context(q.feedback)
    assert "Acme Corp" in ctx
    assert "vendor" in ctx
    assert corrections_as_prompt_context([]) == ""
