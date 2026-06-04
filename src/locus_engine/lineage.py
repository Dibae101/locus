"""Lineage store (Stage 1.5).

A run-scoped, append-only provenance graph keyed by ``cell_id``. It lets any final
cell be resolved back to the original ``SourceLocation``(s) it derived from by
walking lineage edges to the ``extract`` origins. The default implementation is
in-memory; Layer 2 may provide a persistent one for cross-stage runs.

Requirements: 7.10; Property 1 (provenance survival).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from locus_engine.provenance import SourceLocation
from locus_engine.table import Cell


@runtime_checkable
class LineageStore(Protocol):
    """Append-only provenance graph keyed by cell id."""

    def put(self, cell: Cell) -> None: ...
    def get(self, cell_id: str) -> Cell | None: ...
    def resolve_origins(self, cell_id: str) -> list[SourceLocation]: ...


class InMemoryLineageStore:
    """Default in-memory ``LineageStore``."""

    def __init__(self) -> None:
        self._cells: dict[str, Cell] = {}

    def put(self, cell: Cell) -> None:
        self._cells[cell.cell_id] = cell

    def put_all(self, cells: list[Cell]) -> None:
        for c in cells:
            self.put(c)

    def get(self, cell_id: str) -> Cell | None:
        return self._cells.get(cell_id)

    def resolve_origins(self, cell_id: str) -> list[SourceLocation]:
        """Walk lineage edges back to original ``extract`` origins.

        Returns the source locations attached at the earliest ancestors that are
        stored. A cell is treated as an origin when it has no stored parents (its
        own locations are returned). Cycle-safe via a visited set.
        """
        origins: list[SourceLocation] = []
        self._collect(cell_id, origins, set())
        return origins

    def _stored_parents(self, cell: Cell) -> list[str]:
        return [
            pid
            for edge in cell.provenance.lineage
            for pid in edge.parent_cell_ids
            if pid in self._cells
        ]

    def _collect(
        self, cell_id: str, origins: list[SourceLocation], seen: set[str]
    ) -> None:
        if cell_id in seen:
            return
        seen.add(cell_id)
        cell = self._cells.get(cell_id)
        if cell is None:
            return

        # Only follow parents we have not already visited (cycle-safe).
        parents = [pid for pid in self._stored_parents(cell) if pid not in seen]
        if parents:
            for pid in parents:
                self._collect(pid, origins, seen)
        else:
            # No further stored ancestors to walk: treat as an origin and use its
            # own locations. This also covers self/cyclic references.
            origins.extend(cell.provenance.locations)
