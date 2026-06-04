"""Tests for image packaging and the local image store (Stage 6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from locus.artifacts import ArtifactKind, ArtifactType
from locus.errors import ImageNotFoundError
from locus.manifest import ImageManifest
from locus.packaging import pack_image, read_manifest, unpack_image, write_image_dir
from locus.store import LocalImageStore, split_ref


def _manifest(name: str, version: str, *, conformant: bool = True) -> ImageManifest:
    return ImageManifest(
        name=name,
        version=version,
        emits=ArtifactType(kind=ArtifactKind.TABLE),
        provenance_conformant=conformant,
    )


def _build_image(tmp: Path, name: str, version: str) -> Path:
    d = tmp / f"{name}-{version}"
    return write_image_dir(d, _manifest(name, version), {"capability.py": b"# code\n"})


def test_split_ref() -> None:
    assert split_ref("doc-to-tables:1.0") == ("doc-to-tables", "1.0")
    assert split_ref("doc-to-tables") == ("doc-to-tables", None)


def test_write_and_read_manifest(tmp_path: Path) -> None:
    d = _build_image(tmp_path, "img", "1.0.0")
    m = read_manifest(d)
    assert m.name == "img"
    assert (d / "payload" / "capability.py").exists()


def test_pack_unpack_roundtrip(tmp_path: Path) -> None:
    d = _build_image(tmp_path, "img", "1.0.0")
    archive = pack_image(d, tmp_path / "img.tar.gz")
    out = unpack_image(archive, tmp_path / "unpacked")
    assert read_manifest(out).name == "img"


def test_push_pull_roundtrip_and_cache(tmp_path: Path) -> None:
    store = LocalImageStore(root=tmp_path / "registry", cache_dir=tmp_path / "cache")
    img = _build_image(tmp_path, "doc-to-tables", "1.0.0")
    ref = store.push(img)
    assert ref == "doc-to-tables:1.0.0"

    pulled = store.pull("doc-to-tables:1.0.0")
    assert read_manifest(pulled).name == "doc-to-tables"
    # second pull is a cache hit (same path)
    assert store.cached("doc-to-tables:1.0.0") is not None


def test_version_resolution_latest(tmp_path: Path) -> None:
    store = LocalImageStore(root=tmp_path / "registry")
    store.push(_build_image(tmp_path, "img", "1.0.0"))
    store.push(_build_image(tmp_path, "img", "1.10.0"))
    store.push(_build_image(tmp_path, "img", "1.2.0"))
    # semantic: 1.10.0 is the latest, not 1.2.0
    assert store.resolve_version("img", None) == "1.10.0"


def test_pull_unknown_raises(tmp_path: Path) -> None:
    store = LocalImageStore(root=tmp_path / "registry")
    with pytest.raises(ImageNotFoundError):
        store.pull("ghost:1.0")


def test_search_filters_and_lists(tmp_path: Path) -> None:
    store = LocalImageStore(root=tmp_path / "registry")
    store.push(_build_image(tmp_path, "doc-to-tables", "1.0.0"))
    store.push(_build_image(tmp_path, "pii-redactor", "0.1.0"), private=True)

    all_imgs = store.search()
    names = {s.name for s in all_imgs}
    assert names == {"doc-to-tables", "pii-redactor"}

    filtered = store.search("doc")
    assert [s.name for s in filtered] == ["doc-to-tables"]

    # private image is flagged
    pii = next(s for s in all_imgs if s.name == "pii-redactor")
    assert pii.private is True


def test_search_excludes_private_when_unauthorized(tmp_path: Path) -> None:
    store = LocalImageStore(root=tmp_path / "registry")
    store.push(_build_image(tmp_path, "secret", "1.0.0"), private=True)
    assert store.search(include_private=False) == []


def test_private_visibility_persists_across_store_instances(tmp_path: Path) -> None:
    """Req 10.4: a private image stays private for a fresh store (new CLI run)."""
    root = tmp_path / "registry"
    LocalImageStore(root=root).push(_build_image(tmp_path, "secret", "1.0.0"), private=True)

    # fresh instance, as a new CLI invocation would create
    fresh = LocalImageStore(root=root)
    summary = next(s for s in fresh.search() if s.name == "secret")
    assert summary.private is True
    assert fresh.search(include_private=False) == []
