"""Tests for the Cleaner and Deduplicator (Stage 5)."""

from __future__ import annotations

from locus_engine.clean.cleaner import Cleaner
from locus_engine.clean.dedup import Deduplicator
from locus_engine.conformance import (
    assert_merge_retains_locations,
    assert_value_change_triggers_regrounding,
)
from locus_engine.provenance import LineageEdge, OpKind, Provenance, SourceLocation
from locus_engine.table import Cell, ProvenancedTable, Row


def _cell(col: str, value: object, src: str) -> Cell:
    return Cell(
        column=col,
        value=value,
        provenance=Provenance(
            locations=[SourceLocation(source_id=src, index=0)],
            lineage=[LineageEdge(op=OpKind.EXTRACT)],
        ),
    )


def _table(rows: list[dict[str, object]], columns: list[str], src: str = "s1") -> ProvenancedTable:
    built = [Row(cells={c: _cell(c, r[c], src) for c in columns}, source_id=src) for r in rows]
    return ProvenancedTable(columns=columns, rows=built)


def test_cleaner_coerces_types_and_preserves_provenance() -> None:
    table = _table([{"amount": "1,250.50"}], ["amount"])
    cleaner = Cleaner(column_types={"amount": "float"})
    cleaned, errors = cleaner.clean(table)
    assert errors == []
    cell = cleaned.rows[0].cells["amount"]
    assert cell.value == 1250.5
    # provenance preserved + re-grounding marked (value changed)
    assert cell.provenance.locations[0].source_id == "s1"


def test_cleaner_value_change_triggers_regrounding_property() -> None:
    table = _table([{"amount": "100"}], ["amount"])
    before = table.rows[0].cells["amount"]
    cleaned, _ = Cleaner(column_types={"amount": "int"}).clean(table)
    after = cleaned.rows[0].cells["amount"]
    assert_value_change_triggers_regrounding(before, after)


def test_cleaner_coercion_failure_flags_row_and_records_error() -> None:
    table = _table([{"amount": "not-a-number"}], ["amount"])
    cleaned, errors = Cleaner(column_types={"amount": "float"}).clean(table)
    assert len(errors) == 1
    assert "amount" in errors[0]
    assert cleaned.rows[0].flagged is True


def test_cleaner_applies_normalization_rule() -> None:
    table = _table([{"code": "us"}], ["code"])
    cleaner = Cleaner(normalize_rules={"code": lambda v: str(v).upper()})
    cleaned, _ = cleaner.clean(table)
    assert cleaned.rows[0].cells["code"].value == "US"


def test_dedup_disabled_passthrough() -> None:
    table = _table([{"name": "A"}, {"name": "A"}], ["name"])
    out = Deduplicator(keys=[]).dedupe(table)
    assert len(out.rows) == 2


def test_dedup_merges_matching_rows_retaining_locations() -> None:
    a = Row(cells={"name": _cell("name", "Acme Corp", "doc-A")}, source_id="doc-A")
    b = Row(cells={"name": _cell("name", "Acme Corp", "doc-B")}, source_id="doc-B")
    table = ProvenancedTable(columns=["name"], rows=[a, b])
    out = Deduplicator(keys=["name"]).dedupe(table)
    assert len(out.rows) == 1
    merged = out.rows[0].cells["name"]
    assert_merge_retains_locations([a.cells["name"], b.cells["name"]], merged)
    srcs = {loc.source_id for loc in merged.provenance.locations}
    assert srcs == {"doc-A", "doc-B"}


def test_dedup_keeps_distinct_rows() -> None:
    table = _table([{"name": "Acme"}, {"name": "Globex"}], ["name"])
    out = Deduplicator(keys=["name"]).dedupe(table)
    assert len(out.rows) == 2
