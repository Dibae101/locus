"""Cleaner: type coercion and normalization (Stage 5.1).

Coerces each cell to a declared type and applies per-column normalization rules,
always going through ``ProvenanceComposer.map_cell`` so lineage and source locations
are preserved (Req 5.4). A value that cannot be coerced flags the row and records a
coercion error (Req 5.3).

Built-in coercers cover the common scalar types with no heavy dependencies; richer
normalizers (dates, currencies, phones, addresses) are pluggable callables so the
core stays lightweight.

Requirements: 5.1, 5.2, 5.3, 5.4.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from locus_engine.composer import ProvenanceComposer
from locus_engine.table import ProvenancedTable, Row

# A normalization rule maps a raw value to a normalized value.
NormalizeRule = Callable[[Any], Any]


def coerce_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("bool is not an int")
    if isinstance(value, int):
        return value
    text = str(value).strip().replace(",", "")
    return int(float(text)) if ("." in text or "e" in text.lower()) else int(text)


def coerce_float(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    return float(str(value).strip().replace(",", ""))


def coerce_str(value: Any) -> str:
    return str(value).strip()


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "yes", "y", "1"}:
        return True
    if text in {"false", "no", "n", "0"}:
        return False
    raise ValueError(f"cannot coerce {value!r} to bool")


_COERCERS: dict[str, NormalizeRule] = {
    "int": coerce_int,
    "float": coerce_float,
    "str": coerce_str,
    "string": coerce_str,
    "bool": coerce_bool,
}


class CoercionError(Exception):
    """Raised internally when a cell value cannot be coerced (surfaced as a row flag)."""

    def __init__(self, column: str, value: Any) -> None:
        self.column = column
        self.value = value
        super().__init__(f"cannot coerce column {column!r} value {value!r}")


class Cleaner:
    """Applies type coercion and normalization rules to a table."""

    name = "cleaner"

    def __init__(
        self,
        column_types: dict[str, str] | None = None,
        normalize_rules: dict[str, NormalizeRule] | None = None,
    ) -> None:
        self._types = column_types or {}
        self._rules = normalize_rules or {}

    def clean(self, table: ProvenancedTable) -> tuple[ProvenancedTable, list[str]]:
        """Return a cleaned table and a list of coercion error messages.

        Rows with a coercion failure are flagged but retained (the value is left
        unchanged) so the run continues (Req 5.3).
        """
        errors: list[str] = []
        new_rows: list[Row] = []
        for row in table.rows:
            new_cells = {}
            row_flagged = row.flagged
            for col, cell in row.cells.items():
                try:
                    new_value = self._transform(col, cell.value)
                except CoercionError as exc:
                    errors.append(str(exc))
                    row_flagged = True
                    new_cells[col] = cell  # keep original, preserve provenance
                    continue
                new_cells[col] = ProvenanceComposer.map_cell(
                    cell, new_value, detail=f"clean:{col}"
                )
            new_rows.append(
                Row(row_id=row.row_id, cells=new_cells, flagged=row_flagged,
                    source_id=row.source_id)
            )
        return table.model_copy(update={"rows": new_rows}), errors

    def _transform(self, column: str, value: Any) -> Any:
        result = value
        type_name = self._types.get(column)
        if type_name is not None:
            coercer = _COERCERS.get(type_name)
            if coercer is not None:
                try:
                    result = coercer(result)
                except (ValueError, TypeError) as exc:
                    raise CoercionError(column, value) from exc
        rule = self._rules.get(column)
        if rule is not None:
            result = rule(result)
        return result
