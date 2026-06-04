"""Tests for source-location and provenance models (Stage 1.1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from locus_engine.provenance import (
    BBox,
    GroundingMode,
    LineageEdge,
    OpKind,
    Provenance,
    SourceLocation,
    new_id,
)


def test_faithfulness_must_be_in_unit_interval() -> None:
    Provenance(faithfulness=0.0)
    Provenance(faithfulness=1.0)
    with pytest.raises(ValidationError):
        Provenance(faithfulness=1.5)
    with pytest.raises(ValidationError):
        Provenance(faithfulness=-0.1)


def test_provenance_defaults() -> None:
    p = Provenance()
    assert p.locations == []
    assert p.faithfulness is None
    assert p.grounding_mode is GroundingMode.NONE
    assert p.lineage == []
    assert p.flagged is False
    assert p.needs_regrounding is False


def test_source_location_optional_geometry() -> None:
    loc = SourceLocation(source_id="doc-1", index=2)
    assert loc.bbox is None and loc.char_span is None
    loc2 = SourceLocation(source_id="doc-1", index=2, bbox=BBox(page=2, x0=0, y0=0, x1=1, y1=1))
    assert loc2.bbox is not None


def test_round_trip_serialization() -> None:
    p = Provenance(
        locations=[SourceLocation(source_id="s", index=1)],
        faithfulness=0.9,
        grounding_mode=GroundingMode.DEGRADED,
        lineage=[LineageEdge(op=OpKind.EXTRACT)],
    )
    restored = Provenance.model_validate_json(p.model_dump_json())
    assert restored == p


def test_new_id_is_unique() -> None:
    assert new_id() != new_id()
