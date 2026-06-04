"""Source location and provenance models (Stage 1.1).

Provenance is framework-managed: every value the engine produces carries where it
came from (``SourceLocation``), how trustworthy it is (``faithfulness``), and how it
was derived (``lineage``). These types are the foundation the whole engine binds to.

Requirements: 3.3, 3.4, 7.2, 7.5.
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


class BBox(BaseModel):
    """Bounding box in PDF/image coordinate space (points), origin top-left."""

    page: int
    x0: float
    y0: float
    x1: float
    y1: float


class CharSpan(BaseModel):
    """Character offset range within a source's text stream."""

    start: int
    end: int


class SourceLocation(BaseModel):
    """Where a piece of content originated (Req 3.3, 3.4).

    ``source_id`` and ``index`` are always present; ``bbox``/``char_span`` are
    included only when the parser provides positional information.
    """

    source_id: str
    index: int = 0  # page number or record index
    bbox: BBox | None = None
    char_span: CharSpan | None = None
    note: str | None = None  # e.g. "table cell (r2,c3)"


class GroundingMode(StrEnum):
    FULL = "full"  # LLM-as-judge (Req 7.3)
    DEGRADED = "degraded"  # embedding/string similarity (Req 7.4)
    NONE = "none"  # not yet validated


class OpKind(StrEnum):
    EXTRACT = "extract"  # IR -> cell
    MAP = "map"  # 1:1 transform (normalize/coerce)
    MERGE = "merge"  # N:1 (dedup/entity-resolution)
    SPLIT = "split"  # 1:N (one cell -> many)
    MASK = "mask"  # value hidden/redacted, still grounded
    REVIEW = "review"  # human correction


class LineageEdge(BaseModel):
    """One edge in the provenance DAG: how this cell was derived."""

    op: OpKind
    parent_cell_ids: list[str] = Field(default_factory=list)
    detail: str | None = None  # operation-specific note (rule name, reviewer id)


class Provenance(BaseModel):
    """Framework-managed provenance attached to every Cell."""

    locations: list[SourceLocation] = Field(default_factory=list)
    faithfulness: float | None = Field(default=None, ge=0.0, le=1.0)  # Req 7.2
    grounding_mode: GroundingMode = GroundingMode.NONE  # Req 7.5
    lineage: list[LineageEdge] = Field(default_factory=list)
    flagged: bool = False
    needs_regrounding: bool = False


def new_id() -> str:
    """Generate a stable, unique identifier for a cell or row."""
    return uuid.uuid4().hex
