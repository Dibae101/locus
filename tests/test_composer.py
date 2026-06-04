"""Tests for provenance composition (Stage 1.3).

Covers Properties 3 (merge location retention), 4 (mask preserves grounding),
5 (value change triggers re-grounding).
"""

from __future__ import annotations

import pytest

from locus_engine.composer import ProvenanceComposer
from locus_engine.provenance import GroundingMode, OpKind, Provenance, SourceLocation
from locus_engine.table import Cell


def _cell(col: str, value: object, *, src: str, faith: float | None = None) -> Cell:
    return Cell(
        column=col,
        value=value,
        provenance=Provenance(
            locations=[SourceLocation(source_id=src, index=0)],
            faithfulness=faith,
            grounding_mode=GroundingMode.DEGRADED if faith is not None else GroundingMode.NONE,
        ),
    )


def test_map_unchanged_value_does_not_mark_regrounding() -> None:
    src = _cell("amount", 100, src="a", faith=0.9)
    out = ProvenanceComposer.map_cell(src, 100)
    assert out.value == 100
    assert out.provenance.needs_regrounding is False
    assert out.provenance.lineage[-1].op is OpKind.MAP
    assert out.provenance.lineage[-1].parent_cell_ids == [src.cell_id]


def test_map_changed_value_marks_regrounding() -> None:
    """Property 5."""
    src = _cell("amount", "100", src="a", faith=0.9)
    out = ProvenanceComposer.map_cell(src, 100, detail="coerce:int")
    assert out.value == 100
    assert out.provenance.needs_regrounding is True


def test_merge_unions_locations_and_takes_min_faithfulness() -> None:
    """Property 3 + conservative faithfulness."""
    a = _cell("name", "Jon", src="a", faith=0.8)
    b = _cell("name", "Jonathan", src="b", faith=0.6)
    merged = ProvenanceComposer.merge_cells([a, b], "Jonathan", strategy="longest")
    sources = {loc.source_id for loc in merged.provenance.locations}
    assert sources == {"a", "b"}
    assert merged.provenance.faithfulness == 0.6
    assert merged.provenance.lineage[-1].op is OpKind.MERGE
    assert set(merged.provenance.lineage[-1].parent_cell_ids) == {a.cell_id, b.cell_id}


def test_merge_requires_input() -> None:
    with pytest.raises(ValueError):
        ProvenanceComposer.merge_cells([], "x", strategy="noop")


def test_split_children_reference_parent() -> None:
    src = _cell("tags", "a,b,c", src="a", faith=0.7)
    children = ProvenanceComposer.split_cell(src, ["a", "b", "c"])
    assert [c.value for c in children] == ["a", "b", "c"]
    for child in children:
        assert child.provenance.lineage[-1].op is OpKind.SPLIT
        assert child.provenance.lineage[-1].parent_cell_ids == [src.cell_id]
        assert child.provenance.locations[0].source_id == "a"


def test_mask_preserves_faithfulness_and_no_regrounding() -> None:
    """Property 4."""
    src = _cell("ssn", "123-45-6789", src="a", faith=0.95)
    masked = ProvenanceComposer.mask_cell(src, "***-**-****")
    assert masked.value == "***-**-****"
    assert masked.provenance.faithfulness == 0.95
    assert masked.provenance.needs_regrounding is False
    assert masked.provenance.lineage[-1].op is OpKind.MASK
