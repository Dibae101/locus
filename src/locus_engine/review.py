"""Human-in-the-loop review API (Stage 8).

Flagged rows enter a review queue with their provenance. A reviewer corrects a cell
(recorded via an ``OpKind.REVIEW`` lineage edge with reviewer id + timestamp), or
approves a flagged row (included without re-validation). Corrections are stored as
feedback records linking original value, corrected value, and source location; when
enabled, those records are injected into subsequent LLM extraction prompts.

This layer exposes an API only; the interactive UI is Layer 2.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from locus_engine.composer import ProvenanceComposer
from locus_engine.provenance import OpKind, SourceLocation
from locus_engine.table import Cell, Row


class FeedbackRecord(BaseModel):
    """A stored correction linking original/corrected values to the source (Req 9.4)."""

    column: str
    original_value: object
    corrected_value: object
    locations: list[SourceLocation] = Field(default_factory=list)
    reviewer: str
    timestamp: str


class ReviewItem(BaseModel):
    """A flagged row awaiting review, with its provenance."""

    row: Row
    approved: bool = False


class ReviewQueue:
    """Holds flagged rows and records corrections and approvals."""

    def __init__(self) -> None:
        self._items: dict[str, ReviewItem] = {}
        self.feedback: list[FeedbackRecord] = []

    def add_flagged(self, row: Row) -> None:
        """Add a flagged row to the queue with its provenance (Req 9.1)."""
        if row.flagged:
            self._items[row.row_id] = ReviewItem(row=row)

    def add_table_flagged(self, rows: list[Row]) -> None:
        for row in rows:
            self.add_flagged(row)

    @property
    def pending(self) -> list[ReviewItem]:
        return [it for it in self._items.values() if not it.approved]

    def correct(
        self, row_id: str, column: str, new_value: object, *, reviewer: str
    ) -> Cell:
        """Apply a correction to a cell and record feedback (Req 9.2, 9.4)."""
        item = self._items[row_id]
        old_cell = item.row.cells[column]
        timestamp = datetime.now(UTC).isoformat()

        new_cell = ProvenanceComposer.map_cell(
            old_cell, new_value, detail=f"review:{reviewer}"
        )
        # Tag the lineage edge as a REVIEW op explicitly.
        new_cell.provenance.lineage[-1].op = OpKind.REVIEW
        item.row.cells[column] = new_cell

        self.feedback.append(
            FeedbackRecord(
                column=column,
                original_value=old_cell.value,
                corrected_value=new_value,
                locations=[loc.model_copy(deep=True) for loc in old_cell.provenance.locations],
                reviewer=reviewer,
                timestamp=timestamp,
            )
        )
        return new_cell

    def approve(self, row_id: str) -> Row:
        """Approve a flagged row so it is emitted without re-validation (Req 9.3)."""
        item = self._items[row_id]
        item.approved = True
        item.row.flagged = False
        return item.row


def corrections_as_prompt_context(feedback: list[FeedbackRecord]) -> str:
    """Render stored corrections as text for injection into LLM prompts (Req 9.5)."""
    if not feedback:
        return ""
    lines = ["Apply these reviewer corrections learned from earlier rows:"]
    for fb in feedback:
        lines.append(
            f"- column {fb.column!r}: prefer {fb.corrected_value!r} "
            f"over {fb.original_value!r}"
        )
    return "\n".join(lines)
