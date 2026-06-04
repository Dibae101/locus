"""Tests for the pipeline planner: DAG, cycles, static type-check (Stage 4.1/4.2)."""

from __future__ import annotations

import pandas as pd
import pytest

from locus.artifacts import ArtifactKind, ArtifactType
from locus.errors import ConformanceError, CycleError, PlanError, TypeMismatchError
from locus.image import ResolvedImage, StageContext
from locus.locusfile import Locusfile, SourceSpec, StageSpec
from locus.manifest import ImageManifest
from locus.planner import PipelinePlanner


class _StubCap:
    def run(self, inputs: list[pd.DataFrame], ctx: StageContext) -> tuple[pd.DataFrame, str]:
        return pd.DataFrame(), "deterministic"


def _image(
    name: str,
    *,
    accepts: list[ArtifactType] | None = None,
    emits: ArtifactType | None = None,
    conformant: bool = True,
) -> ResolvedImage:
    manifest = ImageManifest(
        name=name,
        version="1.0.0",
        accepts=accepts or [],
        emits=emits or ArtifactType(kind=ArtifactKind.TABLE),
        provenance_conformant=conformant,
    )
    return ResolvedImage(manifest=manifest, capability=_StubCap())


def _resolver(mapping: dict[str, ResolvedImage]):
    return lambda ref: mapping[ref]


def test_linear_pipeline_waves() -> None:
    lf = Locusfile(
        source=SourceSpec(type="files", path="./d"),
        pipeline=[
            StageSpec(id="a", image="ocr"),
            StageSpec(id="b", image="ext", needs=["a"]),
            StageSpec(id="c", image="dedup", needs=["b"]),
        ],
    )
    images = {
        "ocr": _image("ocr", emits=ArtifactType(kind=ArtifactKind.IR)),
        "ext": _image("ext", accepts=[ArtifactType(kind=ArtifactKind.IR)],
                      emits=ArtifactType(kind=ArtifactKind.TABLE)),
        "dedup": _image("dedup", accepts=[ArtifactType(kind=ArtifactKind.TABLE)],
                        emits=ArtifactType(kind=ArtifactKind.TABLE)),
    }
    plan = PipelinePlanner().plan(lf, _resolver(images))
    assert plan.waves == [["a"], ["b"], ["c"]]
    assert plan.terminal == "c"


def test_parallel_branches_share_a_wave() -> None:
    lf = Locusfile(
        source=SourceSpec(type="files", path="./d"),
        pipeline=[
            StageSpec(id="a", image="x"),
            StageSpec(id="b", image="x"),
            StageSpec(id="merge", image="m", needs=["a", "b"]),
        ],
    )
    table = ArtifactType(kind=ArtifactKind.TABLE)
    images = {
        "x": _image("x", emits=table),
        "m": _image("m", accepts=[table], emits=table),
    }
    plan = PipelinePlanner().plan(lf, _resolver(images))
    assert sorted(plan.waves[0]) == ["a", "b"]
    assert plan.waves[1] == ["merge"]


def test_cycle_detected() -> None:
    lf = Locusfile(
        source=SourceSpec(type="files", path="./d"),
        pipeline=[
            StageSpec(id="a", image="x", needs=["b"]),
            StageSpec(id="b", image="x", needs=["a"]),
        ],
    )
    images = {"x": _image("x")}
    with pytest.raises(CycleError):
        PipelinePlanner().plan(lf, _resolver(images))


def test_type_mismatch_fails_fast() -> None:
    lf = Locusfile(
        source=SourceSpec(type="files", path="./d"),
        pipeline=[
            StageSpec(id="a", image="emit_graph"),
            StageSpec(id="b", image="want_table", needs=["a"]),
        ],
    )
    images = {
        "emit_graph": _image("emit_graph", emits=ArtifactType(kind=ArtifactKind.GRAPH)),
        "want_table": _image("want_table", accepts=[ArtifactType(kind=ArtifactKind.TABLE)],
                             emits=ArtifactType(kind=ArtifactKind.TABLE)),
    }
    with pytest.raises(TypeMismatchError):
        PipelinePlanner().plan(lf, _resolver(images))


def test_minor_version_difference_warns_not_fails() -> None:
    lf = Locusfile(
        source=SourceSpec(type="files", path="./d"),
        pipeline=[
            StageSpec(id="a", image="p"),
            StageSpec(id="b", image="c", needs=["a"]),
        ],
    )
    images = {
        "p": _image("p", emits=ArtifactType(kind=ArtifactKind.TABLE, major=1, minor=2)),
        "c": _image("c", accepts=[ArtifactType(kind=ArtifactKind.TABLE, major=1, minor=0)],
                    emits=ArtifactType(kind=ArtifactKind.TABLE)),
    }
    plan = PipelinePlanner().plan(lf, _resolver(images))
    assert any("minor" in w for w in plan.warnings)


def test_non_conformant_fails_in_strict_mode() -> None:
    lf = Locusfile(image="bad:1.0", source=SourceSpec(type="files", path="./d"))
    images = {"bad:1.0": _image("bad", conformant=False)}
    with pytest.raises(ConformanceError):
        PipelinePlanner().plan(lf, _resolver(images), mode="strict")


def test_non_conformant_allowed_in_permissive_mode() -> None:
    lf = Locusfile(image="bad:1.0", source=SourceSpec(type="files", path="./d"))
    images = {"bad:1.0": _image("bad", conformant=False)}
    plan = PipelinePlanner().plan(lf, _resolver(images), mode="permissive")
    assert plan.terminal == "main"


def test_unknown_dependency_raises() -> None:
    lf = Locusfile(
        source=SourceSpec(type="files", path="./d"),
        pipeline=[StageSpec(id="a", image="x", needs=["ghost"])],
    )
    with pytest.raises(PlanError):
        PipelinePlanner().plan(lf, _resolver({"x": _image("x")}))
