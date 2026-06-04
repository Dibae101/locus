"""Tests for image discovery: inspect + visibility (Stage 8)."""

from __future__ import annotations

from pathlib import Path

import pytest

from locus.artifacts import ArtifactKind, ArtifactType
from locus.errors import ImageNotFoundError
from locus.manifest import ImageManifest
from locus.packaging import write_image_dir
from locus.store import LocalImageStore


def _img(tmp: Path, name: str, version: str, *, conformant: bool = True) -> Path:
    m = ImageManifest(
        name=name,
        version=version,
        accepts=[ArtifactType(kind=ArtifactKind.TABLE)],
        emits=ArtifactType(kind=ArtifactKind.TABLE),
        engine_modes=["deterministic", "llm"],
        provenance_conformant=conformant,
    )
    return write_image_dir(tmp / f"{name}-{version}", m, {"c.py": b"#"})


def test_inspect_reports_contract(tmp_path: Path) -> None:
    store = LocalImageStore(root=tmp_path / "reg")
    store.push(_img(tmp_path, "doc-to-tables", "1.0.0"))
    m = store.inspect("doc-to-tables:1.0.0")
    assert m.emits.tag() == "table/v1"
    assert m.accepts[0].tag() == "table/v1"
    assert "llm" in m.engine_modes


def test_inspect_resolves_latest_version(tmp_path: Path) -> None:
    store = LocalImageStore(root=tmp_path / "reg")
    store.push(_img(tmp_path, "img", "1.0.0"))
    store.push(_img(tmp_path, "img", "2.0.0"))
    assert store.inspect("img").version == "2.0.0"


def test_inspect_private_hidden_when_unauthorized(tmp_path: Path) -> None:
    store = LocalImageStore(root=tmp_path / "reg")
    store.push(_img(tmp_path, "secret", "1.0.0"), private=True)
    # authorized sees it
    assert store.inspect("secret:1.0.0", include_private=True).name == "secret"
    # unauthorized discovery cannot
    with pytest.raises(ImageNotFoundError):
        store.inspect("secret:1.0.0", include_private=False)
