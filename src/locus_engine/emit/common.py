"""Shared emit helpers: build the rows + lineage column representation.

Requirements: 8.2, 8.3, 8.4, 8.5, 8.6.
"""

from __future__ import annotations

from typing import Any

from locus_engine.table import ProvenancedTable

LINEAGE_COLUMN = "_lineage"


def cell_provenance_dict(table: ProvenancedTable) -> list[dict[str, Any]]:
    """Per-row lineage payload: each cell's faithfulness + source locations (Req 8.3, 8.5)."""
    payload: list[dict[str, Any]] = []
    for row in table.rows:
        row_lineage: dict[str, Any] = {"_row_flagged": row.flagged}
        for col, cell in row.cells.items():
            prov = cell.provenance
            row_lineage[col] = {
                "faithfulness": prov.faithfulness,
                "grounding_mode": prov.grounding_mode.value,
                "locations": [loc.model_dump(exclude_none=True) for loc in prov.locations],
            }
        payload.append(row_lineage)
    return payload


def records_with_lineage(table: ProvenancedTable) -> list[dict[str, Any]]:
    """Plain value records plus a reserved lineage column (Req 8.3, 8.4)."""
    lineage = cell_provenance_dict(table)
    records: list[dict[str, Any]] = []
    for i, row in enumerate(table.rows):
        record = {col: row.cells[col].value if col in row.cells else None for col in table.columns}
        record[LINEAGE_COLUMN] = lineage[i]
        records.append(record)
    return records
