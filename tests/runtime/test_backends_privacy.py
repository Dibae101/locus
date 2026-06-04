"""Tests for runtime backends and privacy disclosure (Stage 10)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from locus.artifacts import ArtifactKind, ArtifactType
from locus.backends import DockerBackend, ProcessBackend, select_backend
from locus.errors import BackendUnavailableError
from locus.image import ResolvedImage, StageContext
from locus.locusfile import Locusfile, SourceSpec, StageSpec
from locus.manifest import ImageManifest, PrivacyClass
from locus.planner import PipelinePlanner
from locus.privacy import classify_pipeline

CSV = str(Path(__file__).parent.parent / "fixtures" / "invoices.csv")


# --- backends -------------------------------------------------------------


def test_process_backend_available_and_runs() -> None:
    backend = ProcessBackend()
    assert backend.available() is True


def test_select_process_backend() -> None:
    assert select_backend("process").name == "process"


def test_select_docker_backend_errors_when_unavailable(monkeypatch) -> None:
    """Req 1.5: no silent fallback when Docker is absent."""
    monkeypatch.setattr(DockerBackend, "available", lambda self: False)
    with pytest.raises(BackendUnavailableError):
        select_backend("docker")


def test_select_unknown_backend_errors() -> None:
    with pytest.raises(BackendUnavailableError):
        select_backend("podman")


# --- privacy disclosure ---------------------------------------------------


def _image(name: str, privacy: PrivacyClass) -> ResolvedImage:
    class _Cap:
        def run(self, inputs: list[pd.DataFrame], ctx: StageContext) -> tuple[pd.DataFrame, str]:
            return pd.DataFrame(), "deterministic"

    manifest = ImageManifest(
        name=name,
        version="1.0.0",
        emits=ArtifactType(kind=ArtifactKind.TABLE),
        privacy_class=privacy,
        provenance_conformant=True,
    )
    return ResolvedImage(manifest=manifest, capability=_Cap())


def _plan(images: dict[str, ResolvedImage], lf: Locusfile):
    return PipelinePlanner().plan(lf, lambda ref: images[ref])


def test_all_local_pipeline_discloses_local() -> None:
    lf = Locusfile(image="local:1.0", source=SourceSpec(type="files", path=CSV))
    plan = _plan({"local:1.0": _image("local", PrivacyClass.LOCAL_ONLY)}, lf)
    disc = classify_pipeline(plan)
    assert disc.all_local is True
    assert disc.consent_prompt() is None
    assert "no data leaves" in disc.summary()


def test_external_stage_requires_consent_and_no_blanket_local_claim() -> None:
    lf = Locusfile(
        source=SourceSpec(type="files", path=CSV),
        pipeline=[
            StageSpec(id="a", image="local:1.0"),
            StageSpec(id="b", image="ext:1.0", needs=["a"]),
        ],
    )
    images = {
        "local:1.0": _image("local", PrivacyClass.LOCAL_ONLY),
        "ext:1.0": _image("ext", PrivacyClass.CALLS_EXTERNAL),
    }
    # ext accepts table from local
    images["ext:1.0"].manifest.accepts = [ArtifactType(kind=ArtifactKind.TABLE)]
    disc = classify_pipeline(_plan(images, lf))
    assert disc.has_external is True
    assert disc.all_local is False
    assert "b" in disc.stages_external
    prompt = disc.consent_prompt()
    assert prompt is not None and "external" in prompt.lower()
    assert "no data leaves" not in disc.summary()  # Req 12.3
