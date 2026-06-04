"""Tests for the lineage store (Stage 1.5).

Covers Property 1 (provenance survival): a transformed cell resolves back to the
original source location through multi-hop lineage.
"""

from __future__ import annotations

from locus_engine.composer import ProvenanceComposer
from locus_engine.lineage import InMemoryLineageStore
from locus_engine.provenance import LineageEdge, OpKind, Provenance, SourceLocation
from locus_engine.table import Cell


def _origin_cell(value: object, src: str) -> Cell:
    return Cell(
        column="c",
        value=value,
        provenance=Provenance(
            locations=[SourceLocation(source_id=src, index=0)],
            lineage=[LineageEdge(op=OpKind.EXTRACT)],
        ),
    )


def test_resolve_origin_of_extracted_cell() -> None:
    store = InMemoryLineageStore()
    c = _origin_cell("v", "doc-1")
    store.put(c)
    origins = store.resolve_origins(c.cell_id)
    assert [loc.source_id for loc in origins] == ["doc-1"]


def test_resolve_through_map_then_merge() -> None:
    """extract -> map -> merge still resolves to original sources (Property 1)."""
    store = InMemoryLineageStore()

    a = _origin_cell("100", "doc-A")
    b = _origin_cell("100.00", "doc-B")
    store.put_all([a, b])

    a_mapped = ProvenanceComposer.map_cell(a, 100, detail="coerce")
    store.put(a_mapped)

    merged = ProvenanceComposer.merge_cells([a_mapped, b], 100, strategy="numeric")
    store.put(merged)

    origins = {loc.source_id for loc in store.resolve_origins(merged.cell_id)}
    assert origins == {"doc-A", "doc-B"}


def test_missing_cell_resolves_empty() -> None:
    store = InMemoryLineageStore()
    assert store.resolve_origins("does-not-exist") == []


def test_cycle_safe() -> None:
    """A pathological self-referential lineage must not infinitely recurse."""
    store = InMemoryLineageStore()
    c = Cell(
        column="c",
        value="v",
        provenance=Provenance(locations=[SourceLocation(source_id="s", index=0)]),
    )
    # Make the cell reference itself as a parent.
    c.provenance.lineage.append(LineageEdge(op=OpKind.MAP, parent_cell_ids=[c.cell_id]))
    store.put(c)
    # Self-parent is filtered as a stored parent -> recurses once, guarded by seen set.
    origins = store.resolve_origins(c.cell_id)
    assert [loc.source_id for loc in origins] == ["s"]
