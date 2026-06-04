"""Tests for the stage executor and multi-stage composition (Stage 4.3)."""

from __future__ import annotations

from pathlib import Path

from locus.locusfile import Locusfile, SourceSpec, StageSpec
from locus.runner import run_pipeline
from locus.workspace import RunWorkspace

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_single_stage_pipeline_via_planner() -> None:
    lf = Locusfile(
        image="doc-to-tables:0.1.0",
        source=SourceSpec(type="files", path=str(FIXTURES / "invoices.csv")),
    )
    out = run_pipeline(lf, workspace=RunWorkspace())
    assert len(out.frame) == 3
    assert "_lineage" in out.frame.columns


def test_two_stage_pipeline_chains_table_to_table() -> None:
    """doc-to-tables -> drop-flagged composes; output of stage 1 feeds stage 2."""
    lf = Locusfile(
        source=SourceSpec(type="files", path=str(FIXTURES / "invoices.csv")),
        pipeline=[
            StageSpec(id="extract", image="doc-to-tables:0.1.0"),
            StageSpec(id="filter", image="drop-flagged:0.1.0", needs=["extract"]),
        ],
    )
    out = run_pipeline(lf, workspace=RunWorkspace())
    # grounding_threshold default 0.7; CSV grounds perfectly so nothing is flagged/dropped
    assert len(out.frame) == 3
    assert out.artifact.produced_by == "filter"
