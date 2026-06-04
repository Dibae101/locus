"""Dual-engine extractor with reconciliation (Stage 6.4).

Deterministic extraction always runs first (Req 14.1). The LLM engine activates only
when a credential is present (Req 13.2, 13.3). When both run, results are reconciled
so that an LLM value may *fill* a missing/empty deterministic cell, but may NOT
silently override a non-empty deterministic value — a conflict flags the row instead
(Req 14.4). Provenance from the deterministic extraction is preserved; an LLM-derived
value records a MAP lineage edge marking it for re-grounding.

Requirements: 13.1, 13.2, 13.3, 13.4, 14.1, 14.4; Properties 6, 7.
"""

from __future__ import annotations

from locus_engine.composer import ProvenanceComposer
from locus_engine.extract.deterministic import DeterministicEngine
from locus_engine.ir import IntermediateRepresentation
from locus_engine.llm.engine import LLMEngine
from locus_engine.plugins import ExtractContext, ResolvedSchema
from locus_engine.table import ProvenancedTable, Row


def _is_empty(value: object) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


class Extractor:
    """Coordinates deterministic and (optional) LLM extraction."""

    name = "extractor"

    def __init__(
        self,
        deterministic: DeterministicEngine | None = None,
        llm: LLMEngine | None = None,
    ) -> None:
        self._det = deterministic or DeterministicEngine()
        self._llm = llm

    def extract(
        self,
        ir: IntermediateRepresentation,
        schema: ResolvedSchema,
        ctx: ExtractContext,
    ) -> ProvenancedTable:
        det_table = self._det.extract(ir, schema, ctx)  # always first (Req 14.1)

        if not ctx.credential_available or self._llm is None:
            return det_table  # deterministic-only (Req 13.2); no egress (Property 7)

        llm_table = self._llm.map_fields(det_table, schema, ctx)
        return self._reconcile(det_table, llm_table)

    @staticmethod
    def _reconcile(
        det_table: ProvenancedTable, llm_table: ProvenancedTable
    ) -> ProvenancedTable:
        """Merge LLM proposals into the deterministic table under the guardrail:
        LLM may fill empty cells; a conflict on a non-empty cell flags the row and
        keeps the deterministic value (Req 14.4, Property 6)."""
        reconciled_rows: list[Row] = []
        for det_row, llm_row in zip(det_table.rows, llm_table.rows, strict=True):
            new_cells = dict(det_row.cells)
            flagged = det_row.flagged
            for col, det_cell in det_row.cells.items():
                llm_value = llm_row.cells[col].value if col in llm_row.cells else None
                if _is_empty(det_cell.value) and not _is_empty(llm_value):
                    # Fill: record an LLM-derived MAP edge; marks re-grounding.
                    new_cells[col] = ProvenanceComposer.map_cell(
                        det_cell, llm_value, detail="llm:fill"
                    )
                elif (
                    not _is_empty(det_cell.value)
                    and not _is_empty(llm_value)
                    and llm_value != det_cell.value
                ):
                    # Conflict: keep deterministic value, flag the row (no override).
                    flagged = True
            reconciled_rows.append(
                Row(
                    row_id=det_row.row_id,
                    cells=new_cells,
                    flagged=flagged,
                    source_id=det_row.source_id,
                )
            )
        result = det_table.model_copy(update={"rows": reconciled_rows})
        result.produced_by_engine = "llm"
        return result
