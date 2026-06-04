"""Schema inference heuristics (Stage 7.1).

Infer-mode column types from sampled values without an LLM: a lightweight heuristic
layer over the data. Hint mode uses user-provided column names/types to steer
extraction without enforcing full validation. Strict mode (Pydantic) is unchanged.

Requirements: 4.1, 4.2, 4.3.
"""

from __future__ import annotations

import re

_INT_RE = re.compile(r"^[+-]?\d{1,3}(,\d{3})*$|^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?\d+(,\d{3})*(\.\d+)?$|^[+-]?\d*\.\d+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$|^\d{1,2}/\d{1,2}/\d{2,4}$")
_BOOL_VALUES = {"true", "false", "yes", "no", "y", "n"}


def infer_cell_type(value: str) -> str:
    v = value.strip()
    if not v:
        return "str"
    low = v.lower()
    if low in _BOOL_VALUES:
        return "bool"
    if _INT_RE.match(v):
        return "int"
    if _FLOAT_RE.match(v):
        return "float"
    if _DATE_RE.match(v):
        return "date"
    return "str"


def infer_column_types(header: list[str], rows: list[list[str]]) -> dict[str, str]:
    """Infer one type per column from a sample of data rows.

    The chosen type is the most specific type that fits all non-empty samples,
    widening to ``str`` on any disagreement.
    """
    types: dict[str, str] = {}
    # precedence: bool < int < float; date and str are standalone.
    widen = {"int": "float"}
    for i, col in enumerate(header):
        seen: set[str] = set()
        for row in rows:
            if i < len(row) and row[i].strip():
                seen.add(infer_cell_type(row[i]))
        types[col] = _reconcile(seen, widen)
    return types


def _reconcile(seen: set[str], widen: dict[str, str]) -> str:
    if not seen:
        return "str"
    if len(seen) == 1:
        return next(iter(seen))
    # int + float -> float; anything else mixed -> str
    if seen <= {"int", "float"}:
        return "float"
    return "str"
