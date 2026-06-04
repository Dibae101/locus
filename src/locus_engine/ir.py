"""Intermediate Representation (Stage 1.4).

The IR (``ir/v1``) is the parser-agnostic structure every parser emits and every
downstream phase consumes. It preserves text, layout elements, table structure, and
a ``SourceLocation`` on every element. It is the second stable, versioned contract
(alongside ``ProvenancedTable``) that the Layer 2 runtime depends on.

Requirements: 3.1, 3.2, 3.3.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from locus_engine.provenance import SourceLocation

IR_SCHEMA_VERSION = "ir/v1"


class IRElementKind(StrEnum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE = "table"
    LIST = "list"
    KEY_VALUE = "key_value"


class IRTable(BaseModel):
    """Row-and-column structure preserved from the source (Req 3.2)."""

    cells: list[list[str]]  # [row][col] text
    location: SourceLocation


class IRElement(BaseModel):
    """One located content element. Every element carries a SourceLocation (Req 3.3)."""

    kind: IRElementKind
    text: str = ""
    table: IRTable | None = None
    location: SourceLocation


class IntermediateRepresentation(BaseModel):
    """Parser-agnostic normalized content for a single source."""

    schema_version: str = IR_SCHEMA_VERSION
    source_id: str
    content_type: str
    elements: list[IRElement] = Field(default_factory=list)

    def tables(self) -> list[IRElement]:
        return [e for e in self.elements if e.kind is IRElementKind.TABLE]
