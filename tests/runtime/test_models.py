"""Tests for Layer 2 core data models (Stage 1)."""

from __future__ import annotations

from locus.artifacts import ArtifactKind, ArtifactType, Compat, LocusArtifact
from locus.locusfile import Locusfile, SourceSpec, StageSpec
from locus.manifest import ImageManifest, PrivacyClass

# --- ArtifactType compatibility (Req 6.6) ---------------------------------


def test_tag_format() -> None:
    assert ArtifactType(kind=ArtifactKind.TABLE).tag() == "table/v1"
    assert ArtifactType(kind=ArtifactKind.IR, major=2).tag() == "ir/v2"


def test_compat_ok_same_type() -> None:
    a = ArtifactType(kind=ArtifactKind.TABLE, major=1, minor=0)
    b = ArtifactType(kind=ArtifactKind.TABLE, major=1, minor=0)
    assert a.compatible_with(b) is Compat.OK


def test_compat_minor_diff() -> None:
    producer = ArtifactType(kind=ArtifactKind.TABLE, major=1, minor=2)
    consumer = ArtifactType(kind=ArtifactKind.TABLE, major=1, minor=0)
    assert producer.compatible_with(consumer) is Compat.MINOR_DIFF


def test_compat_major_incompatible() -> None:
    producer = ArtifactType(kind=ArtifactKind.TABLE, major=2)
    consumer = ArtifactType(kind=ArtifactKind.TABLE, major=1)
    assert producer.compatible_with(consumer) is Compat.INCOMPATIBLE


def test_compat_kind_incompatible() -> None:
    producer = ArtifactType(kind=ArtifactKind.IR)
    consumer = ArtifactType(kind=ArtifactKind.TABLE)
    assert producer.compatible_with(consumer) is Compat.INCOMPATIBLE


def test_parse_roundtrip() -> None:
    assert ArtifactType.parse("table/v1").tag() == "table/v1"
    t = ArtifactType.parse("ir/v2.3")
    assert (t.kind, t.major, t.minor) == (ArtifactKind.IR, 2, 3)


def test_locus_artifact_fields() -> None:
    art = LocusArtifact(
        type=ArtifactType(kind=ArtifactKind.TABLE),
        payload_path="/ws/stage1.parquet",
        produced_by="stage1",
    )
    assert art.type.tag() == "table/v1"
    assert art.engine_mode == "deterministic"


# --- ImageManifest --------------------------------------------------------


def test_manifest_ref_and_defaults() -> None:
    m = ImageManifest(
        name="doc-to-tables",
        version="1.0.0",
        emits=ArtifactType(kind=ArtifactKind.TABLE),
    )
    assert m.ref == "doc-to-tables:1.0.0"
    assert m.privacy_class is PrivacyClass.LOCAL_ONLY
    assert m.provenance_conformant is False
    assert m.engine_modes == ["deterministic"]


# --- Locusfile ------------------------------------------------------------


def test_single_image_shorthand_expands_to_one_stage() -> None:
    lf = Locusfile(image="doc-to-tables:1.0", source=SourceSpec(type="files", path="./d"))
    stages = lf.normalized_pipeline()
    assert len(stages) == 1
    assert stages[0].id == "main"
    assert stages[0].image == "doc-to-tables:1.0"


def test_explicit_pipeline_preserved() -> None:
    lf = Locusfile(
        source=SourceSpec(type="files", path="./d"),
        pipeline=[
            StageSpec(id="a", image="ocr:1.0"),
            StageSpec(id="b", image="dedup:1.0", needs=["a"]),
        ],
    )
    stages = lf.normalized_pipeline()
    assert [s.id for s in stages] == ["a", "b"]
    assert stages[1].needs == ["a"]


def test_empty_locusfile_has_no_stages() -> None:
    assert Locusfile().normalized_pipeline() == []
