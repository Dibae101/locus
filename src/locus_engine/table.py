"""Provenance-bearing tabular data model (Stage 1.2).

A ``Cell`` is never a bare value; it is value + identity + provenance. ``Row`` and
``ProvenancedTable`` build on it. ``ProvenancedTable`` (``table/v1``) is one of the
two stable, versioned contracts the Layer 2 runtime depends on.

Requirements: 4.7, 8.4, 8.6; Property 9 (schema-version stability).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from locus_engine.provenance import Provenance, new_id

TABLE_SCHEMA_VERSION = "table/v1"

EngineKind = Literal["deterministic", "llm"]


class Cell(BaseModel):
    """A single field value plus its identity and provenance. NOT a bare value."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    cell_id: str = Field(default_factory=new_id)
    column: str
    value: Any
    provenance: Provenance = Field(default_factory=Provenance)


class Row(BaseModel):
    """A record: columns mapped to provenance-bearing cells."""

    row_id: str = Field(default_factory=new_id)
    cells: dict[str, Cell]
    flagged: bool = False  # any cell below threshold (Req 7.6)
    source_id: str | None = None

    def value_dict(self) -> dict[str, Any]:
        """The plain {column: value} view, dropping provenance."""
        return {col: cell.value for col, cell in self.cells.items()}


class ProvenancedTable(BaseModel):
    """The unit of data flowing between phases from Extract onward.

    Versioned via ``schema_version`` (Property 9): a breaking change requires a new
    major version, never a mutation of ``table/v1``.
    """

    schema_version: str = TABLE_SCHEMA_VERSION
    columns: list[str]
    rows: list[Row] = Field(default_factory=list)
    produced_by_engine: EngineKind = "deterministic"  # Req 8.6
    grounding_mode: str = "none"
    inferred_types: dict[str, str] = Field(default_factory=dict)

    def value_records(self) -> list[dict[str, Any]]:
        """All rows as plain {column: value} dicts."""
        return [row.value_dict() for row in self.rows]
