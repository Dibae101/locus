"""Tests for cross-stage provenance (Stage 5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from locus.errors import ConformanceError
from locus.locusfile import Locusfile, SourceSpec, StageSpec
from locus.runner import run_pipeline
from locus.workspace import RunWorkspace

FIXTURES = Path(__file__).parent.parent / "fixtures"
CSV = str(FIXTURES / "invoices.csv")


def test_terminal_provenance_resolves_to_origin_single_stage() -> None:
    lf = Locusfile(image="doc-to-tables:0.1.0", source=SourceSpec(type="files", path=CSV))
    out = run_pipeline(lf, workspace=RunWorkspace())
    assert out.provenance, "expected resolved provenance"
    first = out.provenance[0]
    # every cell resolves to the source csv
    for origin in first.cells.values():
        assert any(s.endswith("invoices.csv") for s in origin.source_ids)
        assert origin.faithfulness is not None


def test_provenance_survives_two_stage_pipeline() -> None:
    """doc-to-tables -> drop-flagged: terminal cells still trace to the source."""
    lf = Locusfile(
        source=SourceSpec(type="files", path=CSV),
        pipeline=[
            StageSpec(id="extract", image="doc-to-tables:0.1.0"),
            StageSpec(id="filter", image="drop-flagged:0.1.0", needs=["extract"]),
        ],
    )
    out = run_pipeline(lf, workspace=RunWorkspace())
    assert len(out.provenance) == 3
    origins = out.provenance[0].origin_source_ids
    assert any(s.endswith("invoices.csv") for s in origins)


def test_strict_mode_rejects_non_conformant_stage() -> None:
    lf = Locusfile(
        source=SourceSpec(type="files", path=CSV),
        mode="strict",
        pipeline=[
            StageSpec(id="extract", image="doc-to-tables:0.1.0"),
            StageSpec(id="strip", image="strip-lineage:0.1.0", needs=["extract"]),
        ],
    )
    with pytest.raises(ConformanceError):
        run_pipeline(lf, workspace=RunWorkspace())


def test_permissive_mode_marks_lineage_broken() -> None:
    lf = Locusfile(
        source=SourceSpec(type="files", path=CSV),
        mode="permissive",
        pipeline=[
            StageSpec(id="extract", image="doc-to-tables:0.1.0"),
            StageSpec(id="strip", image="strip-lineage:0.1.0", needs=["extract"]),
        ],
    )
    out = run_pipeline(lf, workspace=RunWorkspace())
    # terminal cells are lineage-broken (the non-conformant stage dropped lineage)
    assert out.provenance
    assert all(
        cell.lineage_broken for row in out.provenance for cell in row.cells.values()
    )
