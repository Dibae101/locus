"""Consolidated Layer 2 correctness-property suite (Stage 11.1).

Encodes the eight runtime design properties as CI-runnable checks over the real
planner/executor and built-in images.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from locus.artifacts import ArtifactKind, ArtifactType
from locus.errors import ConformanceError, CycleError, TypeMismatchError
from locus.image import ResolvedImage
from locus.locusfile import Locusfile, SourceSpec, StageSpec
from locus.manifest import ImageManifest, PrivacyClass
from locus.planner import PipelinePlanner
from locus.privacy import classify_pipeline
from locus.runner import run_pipeline
from locus.store import LocalImageStore
from locus.workspace import RunWorkspace

CSV = str(Path(__file__).parent.parent / "fixtures" / "invoices.csv")


def _resolver(images: dict[str, ResolvedImage]):
    return lambda ref: images[ref]


def _img(name, accepts, emits, conformant=True, privacy=PrivacyClass.LOCAL_ONLY):
    import pandas as pd

    from locus.image import StageContext

    class _Cap:
        def run(self, inputs: list, ctx: StageContext) -> tuple:
            return pd.DataFrame(), "deterministic"

    return ResolvedImage(
        manifest=ImageManifest(
            name=name, version="1.0.0", accepts=accepts, emits=emits,
            provenance_conformant=conformant, privacy_class=privacy,
        ),
        capability=_Cap(),
    )


# Property 1: fail-fast type safety
def test_property_1_type_safety() -> None:
    lf = Locusfile(
        source=SourceSpec(type="files", path=CSV),
        pipeline=[StageSpec(id="a", image="g"), StageSpec(id="b", image="t", needs=["a"])],
    )
    images = {
        "g": _img("g", [], ArtifactType(kind=ArtifactKind.GRAPH)),
        "t": _img(
            "t",
            [ArtifactType(kind=ArtifactKind.TABLE)],
            ArtifactType(kind=ArtifactKind.TABLE),
        ),
    }
    with pytest.raises(TypeMismatchError):
        PipelinePlanner().plan(lf, _resolver(images))


# Property 2: acyclic execution
def test_property_2_acyclic() -> None:
    lf = Locusfile(
        source=SourceSpec(type="files", path=CSV),
        pipeline=[
            StageSpec(id="a", image="x", needs=["b"]),
            StageSpec(id="b", image="x", needs=["a"]),
        ],
    )
    images = {"x": _img("x", [], ArtifactType(kind=ArtifactKind.TABLE))}
    with pytest.raises(CycleError):
        PipelinePlanner().plan(lf, _resolver(images))


# Property 3: dependency ordering
def test_property_3_dependency_ordering() -> None:
    lf = Locusfile(
        source=SourceSpec(type="files", path=CSV),
        pipeline=[
            StageSpec(id="extract", image="doc-to-tables:0.1.0"),
            StageSpec(id="filter", image="drop-flagged:0.1.0", needs=["extract"]),
        ],
    )
    out = run_pipeline(lf, workspace=RunWorkspace())
    assert out.artifact.produced_by == "filter"


# Property 4: end-to-end provenance survival
def test_property_4_provenance_survival() -> None:
    lf = Locusfile(
        source=SourceSpec(type="files", path=CSV),
        pipeline=[
            StageSpec(id="extract", image="doc-to-tables:0.1.0"),
            StageSpec(id="filter", image="drop-flagged:0.1.0", needs=["extract"]),
        ],
    )
    out = run_pipeline(lf, workspace=RunWorkspace())
    assert all(
        any(s.endswith("invoices.csv") for s in row.origin_source_ids)
        for row in out.provenance
    )


# Property 5: conformance gating
def test_property_5_conformance_gating() -> None:
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


# Property 6: credential locality (raw key rejected by loader)
def test_property_6_credential_locality(tmp_path: Path) -> None:
    from locus.errors import CredentialError
    from locus.loader import load_locusfile

    lf = tmp_path / "locusfile.yaml"
    lf.write_text(
        "image: x:1.0\nsource:\n  type: files\n  path: ./d\n"
        "llm:\n  api_key: sk-abcdefghijklmnop1234567890\n"
    )
    with pytest.raises(CredentialError):
        load_locusfile(lf)


# Property 7: registry/credential separation (store has no LLM credential surface)
def test_property_7_registry_credential_separation(tmp_path: Path) -> None:
    store = LocalImageStore(root=tmp_path / "reg")
    # The store API exposes only image operations, never LLM credentials.
    assert not any("key" in attr.lower() for attr in dir(store) if not attr.startswith("_"))


# Property 8: privacy disclosure honesty
def test_property_8_privacy_disclosure() -> None:
    lf = Locusfile(
        source=SourceSpec(type="files", path=CSV),
        pipeline=[
            StageSpec(id="a", image="local"),
            StageSpec(id="b", image="ext", needs=["a"]),
        ],
    )
    table = ArtifactType(kind=ArtifactKind.TABLE)
    images = {
        "local": _img("local", [], table),
        "ext": _img("ext", [table], table, privacy=PrivacyClass.CALLS_EXTERNAL),
    }
    disc = classify_pipeline(PipelinePlanner().plan(lf, _resolver(images)))
    assert disc.consent_prompt() is not None
    assert "no data leaves" not in disc.summary()
