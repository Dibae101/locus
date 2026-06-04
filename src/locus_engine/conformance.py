"""Provenance conformance harness (Stage 4) — the critical guard.

These reusable assertions verify the engine's core correctness properties against
any component or table. The most important is provenance survival (Property 1): a
component that drops lineage is a failing build, not a warning. Layer 2 reuses this
harness to certify third-party images as ``provenance-conformant``.

Covers Properties 1, 2, 3, 4, 5, 8.
"""

from __future__ import annotations

from locus_engine.lineage import InMemoryLineageStore, LineageStore
from locus_engine.provenance import (
    GroundingMode,
    LineageEdge,
    OpKind,
    Provenance,
    SourceLocation,
)
from locus_engine.table import Cell, ProvenancedTable


class ConformanceError(AssertionError):
    """Raised when a provenance/correctness property is violated."""


# --- Property 1: provenance survival --------------------------------------


def assert_table_provenance_survives(
    table: ProvenancedTable, store: LineageStore
) -> None:
    """Every cell in the table must resolve to at least one origin SourceLocation
    through the lineage store (Property 1)."""
    for row in table.rows:
        for col, cell in row.cells.items():
            origins = store.resolve_origins(cell.cell_id)
            if not origins:
                raise ConformanceError(
                    f"cell {col!r} (id={cell.cell_id}) resolves to no source origin"
                )


def assert_cell_provenance_survives(cell: Cell, store: LineageStore) -> None:
    origins = store.resolve_origins(cell.cell_id)
    if not origins:
        raise ConformanceError(
            f"cell {cell.column!r} (id={cell.cell_id}) resolves to no source origin"
        )


# --- Property 2: faithfulness bounds --------------------------------------


def assert_faithfulness_bounds(table: ProvenancedTable, *, validated: bool) -> None:
    """Validated cells must have faithfulness in [0,1] and a non-NONE mode."""
    for row in table.rows:
        for col, cell in row.cells.items():
            f = cell.provenance.faithfulness
            if validated:
                if f is None or not (0.0 <= f <= 1.0):
                    raise ConformanceError(
                        f"cell {col!r} faithfulness {f!r} not in [0,1]"
                    )
                if cell.provenance.grounding_mode is GroundingMode.NONE:
                    raise ConformanceError(
                        f"validated cell {col!r} has grounding_mode NONE"
                    )


# --- Property 3/4/5: composition invariants -------------------------------


def assert_merge_retains_locations(inputs: list[Cell], merged: Cell) -> None:
    """A merged cell's locations must be a superset of all contributors' (Property 3)."""
    want = {
        (loc.source_id, loc.index)
        for c in inputs
        for loc in c.provenance.locations
    }
    have = {(loc.source_id, loc.index) for loc in merged.provenance.locations}
    missing = want - have
    if missing:
        raise ConformanceError(f"merge dropped source locations: {missing}")


def assert_mask_preserves_grounding(before: Cell, after: Cell) -> None:
    """Mask must not lower/clear faithfulness or set needs_regrounding (Property 4)."""
    if after.provenance.faithfulness != before.provenance.faithfulness:
        raise ConformanceError("mask changed faithfulness")
    if after.provenance.needs_regrounding:
        raise ConformanceError("mask set needs_regrounding")


def assert_value_change_triggers_regrounding(before: Cell, after: Cell) -> None:
    """A map that changes value must mark needs_regrounding (Property 5)."""
    if after.value != before.value and not after.provenance.needs_regrounding:
        raise ConformanceError("value changed but needs_regrounding not set")


# --- composite component probe --------------------------------------------


def probe_extraction_engine(engine: object, ir: object, schema: object, ctx: object) -> None:
    """Run an extraction engine on a known provenanced IR and assert every produced
    cell resolves to a source origin. Used to certify a component is conformant.

    ``engine`` must expose ``extract(ir, schema, ctx) -> ProvenancedTable``.
    """
    extract = getattr(engine, "extract", None)
    if not callable(extract):
        raise ConformanceError("engine has no callable extract()")
    table = extract(ir, schema, ctx)
    store = InMemoryLineageStore()
    for row in table.rows:
        store.put_all(list(row.cells.values()))
    assert_table_provenance_survives(table, store)


def make_seeded_cell(value: object, source_id: str) -> Cell:
    """A known origin cell for harness inputs."""
    return Cell(
        column="c",
        value=value,
        provenance=Provenance(
            locations=[SourceLocation(source_id=source_id, index=0)],
            lineage=[LineageEdge(op=OpKind.EXTRACT)],
        ),
    )


__all__ = [
    "ConformanceError",
    "assert_table_provenance_survives",
    "assert_cell_provenance_survives",
    "assert_faithfulness_bounds",
    "assert_merge_retains_locations",
    "assert_mask_preserves_grounding",
    "assert_value_change_triggers_regrounding",
    "probe_extraction_engine",
    "make_seeded_cell",
]
