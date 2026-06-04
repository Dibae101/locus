"""Provenance composition (Stage 1.3) — the central mechanism.

These static rules define how lineage and faithfulness compose for each kind of
transform. Plugins call these primitives instead of mutating cell values directly,
so lineage propagates automatically; bypassing them is the only way to break
provenance, and the conformance harness (Stage 4) detects that.

Composition policy (see design.md):
- map (1:1):   carry parent provenance; value change marks needs_regrounding.
- merge (N:1): union all source locations; faithfulness = min of contributors.
- split (1:N): each child references the originating cell.
- mask:        value hidden but faithfulness PRESERVED (it was grounded).

Requirements: 5.4, 6.3, 7.10; Properties 3, 4, 5.
"""

from __future__ import annotations

from typing import Any

from locus_engine.provenance import LineageEdge, OpKind, Provenance
from locus_engine.table import Cell


class ProvenanceComposer:
    """Static composition rules. Centralizes the policy so it changes in one place."""

    @staticmethod
    def map_cell(
        src: Cell,
        new_value: Any,
        *,
        column: str | None = None,
        detail: str | None = None,
    ) -> Cell:
        """1:1 transform (normalize/coerce). Carries provenance; a value change
        marks the result for re-grounding so a stale score is never emitted."""
        prov = src.provenance.model_copy(deep=True)
        prov.lineage.append(
            LineageEdge(op=OpKind.MAP, parent_cell_ids=[src.cell_id], detail=detail)
        )
        if new_value != src.value:
            prov.needs_regrounding = True
        return Cell(column=column or src.column, value=new_value, provenance=prov)

    @staticmethod
    def merge_cells(cells: list[Cell], chosen_value: Any, *, strategy: str) -> Cell:
        """N:1 merge (dedup/entity resolution). Retains ALL contributing source
        locations (Req 6.3); faithfulness = min of contributors (conservative)."""
        if not cells:
            raise ValueError("merge_cells requires at least one input cell")
        prov = Provenance()
        for c in cells:
            prov.locations.extend(loc.model_copy(deep=True) for loc in c.provenance.locations)
        scores = [
            c.provenance.faithfulness
            for c in cells
            if c.provenance.faithfulness is not None
        ]
        prov.faithfulness = min(scores) if scores else None
        prov.lineage.append(
            LineageEdge(
                op=OpKind.MERGE,
                parent_cell_ids=[c.cell_id for c in cells],
                detail=strategy,
            )
        )
        return Cell(column=cells[0].column, value=chosen_value, provenance=prov)

    @staticmethod
    def split_cell(src: Cell, values: list[Any]) -> list[Cell]:
        """1:N. Each child references the originating cell and carries its locations."""
        out: list[Cell] = []
        for v in values:
            prov = src.provenance.model_copy(deep=True)
            prov.lineage.append(
                LineageEdge(op=OpKind.SPLIT, parent_cell_ids=[src.cell_id])
            )
            out.append(Cell(column=src.column, value=v, provenance=prov))
        return out

    @staticmethod
    def mask_cell(src: Cell, masked_value: Any, *, detail: str = "redacted") -> Cell:
        """Mask/redact. Value hidden but faithfulness PRESERVED and no re-grounding:
        the value was grounded before being hidden (Property 4)."""
        prov = src.provenance.model_copy(deep=True)
        prov.lineage.append(
            LineageEdge(op=OpKind.MASK, parent_cell_ids=[src.cell_id], detail=detail)
        )
        return Cell(column=src.column, value=masked_value, provenance=prov)
