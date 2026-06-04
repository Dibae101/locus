"""Tests for schema inference heuristics (Stage 7.1)."""

from __future__ import annotations

from locus_engine.schema_infer import infer_cell_type, infer_column_types


def test_infer_cell_types() -> None:
    assert infer_cell_type("42") == "int"
    assert infer_cell_type("1,250") == "int"
    assert infer_cell_type("3.14") == "float"
    assert infer_cell_type("1,250.50") == "float"
    assert infer_cell_type("2026-06-04") == "date"
    assert infer_cell_type("true") == "bool"
    assert infer_cell_type("Acme Corp") == "str"
    assert infer_cell_type("") == "str"


def test_infer_column_types_consistent() -> None:
    header = ["name", "amount", "active"]
    rows = [["Acme", "100", "true"], ["Globex", "200", "false"]]
    types = infer_column_types(header, rows)
    assert types == {"name": "str", "amount": "int", "active": "bool"}


def test_infer_widens_int_and_float_to_float() -> None:
    header = ["v"]
    rows = [["100"], ["3.5"]]
    assert infer_column_types(header, rows) == {"v": "float"}


def test_infer_mixed_unrelated_falls_back_to_str() -> None:
    header = ["v"]
    rows = [["100"], ["abc"]]
    assert infer_column_types(header, rows) == {"v": "str"}
