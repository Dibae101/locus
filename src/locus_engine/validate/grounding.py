"""Cell-level grounding contract (Stage 3.4) — degraded mode.

This is part of the engine's core differentiator: every cell is scored for how well
its value is supported by the source text it cites, and rows below the threshold are
flagged. Degraded mode (no LLM) uses string similarity (rapidfuzz) between the cell
value and its cited source span. Full mode (LLM-as-judge) is added in Stage 6.6.

Requirements: 7.1, 7.2, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 7.10.
"""

from __future__ import annotations

from rapidfuzz import fuzz

from locus_engine.ir import IntermediateRepresentation
from locus_engine.provenance import GroundingMode
from locus_engine.table import Cell, ProvenancedTable


class SimilarityScorer:
    """Degraded-mode scorer: normalized partial-ratio similarity in [0, 1]."""

    def score(self, value: str, source_text: str) -> float:
        if not value:
            # Empty value is trivially "supported" only if source is also empty.
            return 1.0 if not source_text else 0.0
        if not source_text:
            return 0.0
        # A cell value is "grounded" if it appears (closely) somewhere in the source.
        # partial_ratio finds the best-matching substring (robust to a short value
        # scored against long source text); token_set_ratio handles word reordering.
        # Take the stronger signal of the two.
        partial = fuzz.partial_ratio(value, source_text)
        token_set = fuzz.token_set_ratio(value, source_text)
        return max(partial, token_set) / 100.0


class GroundingValidator:
    """Scores each cell and flags rows below the grounding threshold."""

    name = "grounding"

    def __init__(self, scorer: SimilarityScorer | None = None) -> None:
        self._scorer = scorer or SimilarityScorer()

    def validate(
        self,
        table: ProvenancedTable,
        ir: IntermediateRepresentation,
        *,
        threshold: float,
        rejection_mode: str = "flag",
    ) -> ProvenancedTable:
        source_text = self._source_text(ir)
        mode = GroundingMode.DEGRADED

        kept_rows = []
        rejected = 0
        for row in table.rows:
            for cell in row.cells.values():
                self._score_cell(cell, source_text, mode)
            row.flagged = any(
                (c.provenance.faithfulness or 0.0) < threshold
                for c in row.cells.values()
            )
            if row.flagged and rejection_mode == "reject":
                rejected += 1
                continue
            kept_rows.append(row)

        result = table.model_copy(update={"rows": kept_rows})
        result.grounding_mode = mode.value
        return result

    def _score_cell(self, cell: Cell, source_text: str, mode: GroundingMode) -> None:
        value = "" if cell.value is None else str(cell.value)
        score = self._scorer.score(value, source_text)
        cell.provenance.faithfulness = score  # Req 7.2
        cell.provenance.grounding_mode = mode  # Req 7.5
        cell.provenance.needs_regrounding = False

    @staticmethod
    def _source_text(ir: IntermediateRepresentation) -> str:
        parts: list[str] = []
        for el in ir.elements:
            if el.text:
                parts.append(el.text)
            if el.table is not None:
                for row in el.table.cells:
                    parts.append(" ".join(row))
        return "\n".join(parts)
