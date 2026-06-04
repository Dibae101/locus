"""Deterministic extraction engine (Stage 3.3).

Derives rows from an IR table without any LLM. The first IR table is interpreted as
a header row + data rows. Each produced cell records an ``extract`` lineage edge and
the table's ``SourceLocation`` (Req 4.7), so provenance is established at origin.

Schema modes:
- **infer** (default): columns taken from the table header.
- **strict**: a user Pydantic model validates each row; failures retry up to the
  configured limit, then record a validation-failure error (Req 4.5, 4.6).

Requirements: 4.1, 4.2, 4.4, 4.5, 4.6, 4.7.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from locus_engine.errors import ExtractionError
from locus_engine.ir import IntermediateRepresentation
from locus_engine.plugins import ExtractContext, ResolvedSchema
from locus_engine.provenance import LineageEdge, OpKind, Provenance, SourceLocation
from locus_engine.schema_infer import infer_column_types
from locus_engine.table import Cell, ProvenancedTable, Row


class DeterministicEngine:
    """Default, LLM-free extraction engine."""

    name = "deterministic"

    def extract(
        self,
        ir: IntermediateRepresentation,
        schema: ResolvedSchema,
        ctx: ExtractContext,
    ) -> ProvenancedTable:
        tables = ir.tables()
        if not tables:
            raise ExtractionError(ir.source_id, "no table found in source")

        table_el = tables[0]
        assert table_el.table is not None
        grid = table_el.table.cells
        location = table_el.table.location
        if len(grid) < 1:
            raise ExtractionError(ir.source_id, "table has no header row")

        header = [c.strip() for c in grid[0]]
        data_rows = grid[1:]

        columns = self._resolve_columns(header, schema)
        inferred = (
            infer_column_types(columns, data_rows) if schema.mode == "infer" else {}
        )
        rows: list[Row] = []
        for raw_row in data_rows:
            row = self._build_row(raw_row, columns, location, ir.source_id)
            if schema.mode == "strict" and schema.model is not None:
                self._validate_strict(row, schema.model, ir.source_id, ctx.retry_limit)
            rows.append(row)

        return ProvenancedTable(
            columns=columns,
            rows=rows,
            produced_by_engine="deterministic",
            inferred_types=inferred,
        )

    @staticmethod
    def _resolve_columns(header: list[str], schema: ResolvedSchema) -> list[str]:
        if schema.mode in ("hint", "strict") and schema.columns:
            return list(schema.columns)
        return header

    @staticmethod
    def _build_row(
        raw_row: list[str],
        columns: list[str],
        location: SourceLocation,
        source_id: str,
    ) -> Row:
        cells: dict[str, Cell] = {}
        for i, col in enumerate(columns):
            value: Any = raw_row[i].strip() if i < len(raw_row) else None
            cells[col] = Cell(
                column=col,
                value=value,
                provenance=Provenance(
                    locations=[location.model_copy(deep=True)],
                    lineage=[LineageEdge(op=OpKind.EXTRACT)],
                ),
            )
        return Row(cells=cells, source_id=source_id)

    @staticmethod
    def _validate_strict(
        row: Row, model: type[BaseModel], source_id: str, retry_limit: int
    ) -> None:
        """Validate a row against a Pydantic model. Deterministic extraction cannot
        'retry' the value (there is no LLM), so a failure after the first attempt is
        recorded; the retry budget is honored by the LLM engine instead."""
        attempts = 1 + max(0, retry_limit)
        last_error: ValidationError | None = None
        for _ in range(attempts):
            try:
                model.model_validate(row.value_dict())
                return
            except ValidationError as exc:
                last_error = exc
                break  # deterministic: re-attempt would be identical
        if last_error is not None:
            row.flagged = True
            raise ExtractionError(source_id, f"schema validation failed: {last_error}")
