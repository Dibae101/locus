"""Cross-stage provenance (Layer 2, Stage 5).

Provenance is established per cell by the Layer 1 engine and carried between stages
in the artifact's ``_lineage`` column. This component records each stage's lineage
into a run-scoped store, resolves the terminal result's cells back to their original
source locations across all stages, and handles permissive-mode lineage-breaking when
a stage is not provenance-conformant.

A stage is conformant when it preserves the ``_lineage`` column (the engine's emitter
does this, and build-time certification verifies it). A non-conformant stage drops the
column; in strict mode the planner already fails the run, in permissive mode this
component marks the affected downstream cells as lineage-broken.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.8.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from locus.emit_constants import LINEAGE_COLUMN


@dataclass
class CellOrigin:
    """Resolved origin of one terminal cell."""

    column: str
    source_ids: list[str]
    faithfulness: float | None
    grounding_mode: str
    lineage_broken: bool = False


@dataclass
class RowProvenance:
    row_index: int
    cells: dict[str, CellOrigin]
    flagged: bool = False

    @property
    def origin_source_ids(self) -> set[str]:
        out: set[str] = set()
        for cell in self.cells.values():
            out.update(cell.source_ids)
        return out


@dataclass
class CrossStageProvenance:
    """Run-scoped record of provenance across all stages of a pipeline."""

    stage_lineage: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def record_stage(self, stage_id: str, frame: pd.DataFrame) -> None:
        """Capture a stage's per-row lineage payloads (Req 7.5)."""
        if LINEAGE_COLUMN in frame.columns:
            self.stage_lineage[stage_id] = list(frame[LINEAGE_COLUMN])
        else:
            self.stage_lineage[stage_id] = []

    @staticmethod
    def mark_lineage_broken(frame: pd.DataFrame) -> pd.DataFrame:
        """Permissive mode: mark a non-conformant stage's output cells lineage-broken
        (Req 7.8). Adds/overwrites the lineage column with a broken marker."""
        result = frame.copy()
        data_cols = [c for c in result.columns if c != LINEAGE_COLUMN]
        broken = []
        for _ in range(len(result)):
            payload: dict[str, Any] = {"_row_flagged": True, "_lineage_broken": True}
            for col in data_cols:
                payload[col] = {
                    "faithfulness": None,
                    "grounding_mode": "none",
                    "locations": [],
                    "lineage_broken": True,
                }
            broken.append(payload)
        result[LINEAGE_COLUMN] = pd.Series(broken, index=result.index, dtype=object)
        return result

    def resolve_terminal(self, frame: pd.DataFrame) -> list[RowProvenance]:
        """Resolve each terminal cell to its origin source locations (Req 7.6).

        Because conformant stages carry the ``_lineage`` column through, the origin
        locations recorded at extraction survive into the terminal frame.
        """
        rows: list[RowProvenance] = []
        data_cols = [c for c in frame.columns if c != LINEAGE_COLUMN]
        lineage_series = (
            list(frame[LINEAGE_COLUMN]) if LINEAGE_COLUMN in frame.columns else []
        )
        for i in range(len(frame)):
            lineage = lineage_series[i] if i < len(lineage_series) else {}
            lineage = lineage if isinstance(lineage, dict) else {}
            cells: dict[str, CellOrigin] = {}
            for col in data_cols:
                meta = lineage.get(col, {}) if isinstance(lineage, dict) else {}
                meta = meta if isinstance(meta, dict) else {}
                locations = meta.get("locations", []) or []
                source_ids = [
                    loc.get("source_id", "")
                    for loc in locations
                    if isinstance(loc, dict)
                ]
                cells[col] = CellOrigin(
                    column=col,
                    source_ids=[s for s in source_ids if s],
                    faithfulness=meta.get("faithfulness"),
                    grounding_mode=meta.get("grounding_mode", "none"),
                    lineage_broken=bool(meta.get("lineage_broken", False)),
                )
            rows.append(
                RowProvenance(
                    row_index=i,
                    cells=cells,
                    flagged=bool(lineage.get("_row_flagged", False)),
                )
            )
        return rows
