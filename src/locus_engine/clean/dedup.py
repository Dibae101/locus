"""Deduplicator (Stage 5.2).

Identifies rows that refer to the same entity by configured matching keys, then
merges each matching set into one row via ``ProvenanceComposer.merge_cells`` so all
contributing source locations are retained (Req 6.3). Disabled config = passthrough
(Req 6.4). The default matcher uses rapidfuzz similarity on the concatenated key
values with a configurable threshold.

Requirements: 6.1, 6.2, 6.3, 6.4.
"""

from __future__ import annotations

from rapidfuzz import fuzz

from locus_engine.composer import ProvenanceComposer
from locus_engine.table import Cell, ProvenancedTable, Row


class Deduplicator:
    """Blocks and merges duplicate rows."""

    name = "deduplicator"

    def __init__(
        self,
        keys: list[str],
        *,
        threshold: float = 0.92,
        strategy: str = "first",
    ) -> None:
        self._keys = keys
        self._threshold = threshold
        self._strategy = strategy

    def dedupe(self, table: ProvenancedTable) -> ProvenancedTable:
        if not self._keys or not table.rows:
            return table

        clusters: list[list[Row]] = []
        for row in table.rows:
            placed = False
            for cluster in clusters:
                if self._matches(row, cluster[0]):
                    cluster.append(row)
                    placed = True
                    break
            if not placed:
                clusters.append([row])

        merged_rows = [self._merge_cluster(c, table.columns) for c in clusters]
        return table.model_copy(update={"rows": merged_rows})

    def _key_string(self, row: Row) -> str:
        return " ".join(
            str(row.cells[k].value) for k in self._keys if k in row.cells
        ).lower()

    def _matches(self, a: Row, b: Row) -> bool:
        ka, kb = self._key_string(a), self._key_string(b)
        if not ka or not kb:
            return False
        return fuzz.token_set_ratio(ka, kb) / 100.0 >= self._threshold

    def _merge_cluster(self, cluster: list[Row], columns: list[str]) -> Row:
        if len(cluster) == 1:
            return cluster[0]
        merged_cells: dict[str, Cell] = {}
        for col in columns:
            contributing = [r.cells[col] for r in cluster if col in r.cells]
            if not contributing:
                continue
            chosen = self._choose(contributing)
            merged_cells[col] = ProvenanceComposer.merge_cells(
                contributing, chosen, strategy=self._strategy
            )
        return Row(
            cells=merged_cells,
            flagged=any(r.flagged for r in cluster),
            source_id=cluster[0].source_id,
        )

    def _choose(self, cells: list[Cell]) -> object:
        if self._strategy == "longest":
            return max((c.value for c in cells), key=lambda v: len(str(v)))
        # default "first"
        return cells[0].value
