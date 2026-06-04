"""Tests for the OCI/Harbor-backed image store using a fake oras client.

The fake client emulates an OCI registry in-memory: push records an artifact (archive
bytes + annotations) under a target ref; pull writes the archive back out; get_tags /
get_manifest read the recorded metadata. This exercises the full OrasImageStore logic
without a live registry.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from locus.artifacts import ArtifactKind, ArtifactType
from locus.errors import ImageNotFoundError
from locus.manifest import ImageManifest
from locus.oci_store import (
    MANIFEST_ANNOTATION,
    VISIBILITY_ANNOTATION,
    OrasImageStore,
)
from locus.packaging import read_manifest, write_image_dir


class FakeOrasClient:
    """In-memory stand-in for oras.client.OrasClient."""

    def __init__(self) -> None:
        # target -> {"archive": bytes, "annotations": {...}}
        self.store: dict[str, dict] = {}
        self.logged_in = False

    def login(self, username: str, password: str, hostname: str | None = None) -> None:
        self.logged_in = True

    def push(self, target, files=None, manifest_annotations=None, **kw):
        archive_spec = files[0]
        archive_path = archive_spec.split(":")[0] if ":" in archive_spec else archive_spec
        # store the archive bytes (registry-side storage survives temp-dir cleanup)
        data = Path(archive_path).read_bytes()
        self.store[target] = {"archive": data, "annotations": dict(manifest_annotations or {})}
        return {"status": "ok"}

    def pull(self, target, outdir=None, overwrite=True, **kw):
        if target not in self.store:
            raise RuntimeError("not found")
        dest = Path(outdir) / "image.tar.gz"
        dest.write_bytes(self.store[target]["archive"])
        return [str(dest)]

    def get_tags(self, repo):
        prefix = repo + ":"
        return [t.split(":", 1)[1] for t in self.store if t.startswith(prefix)]

    def get_manifest(self, target):
        if target not in self.store:
            raise RuntimeError("not found")
        return {"annotations": self.store[target]["annotations"]}


def _image(tmp: Path, name: str, version: str, *, conformant: bool = True) -> Path:
    m = ImageManifest(
        name=name,
        version=version,
        accepts=[ArtifactType(kind=ArtifactKind.TABLE)],
        emits=ArtifactType(kind=ArtifactKind.TABLE),
        provenance_conformant=conformant,
    )
    return write_image_dir(tmp / f"{name}-{version}", m, {"capability.py": b"# code\n"})


def _store(tmp: Path) -> tuple[OrasImageStore, FakeOrasClient]:
    fake = FakeOrasClient()
    store = OrasImageStore(
        "hub.locus.test", namespace="library", cache_dir=tmp / "cache", client=fake
    )
    return store, fake


def test_push_records_artifact_and_annotations(tmp_path: Path) -> None:
    store, fake = _store(tmp_path)
    ref = store.push(_image(tmp_path, "doc-to-tables", "1.0.0"))
    assert ref == "doc-to-tables:1.0.0"
    target = "hub.locus.test/library/doc-to-tables:1.0.0"
    assert target in fake.store
    ann = fake.store[target]["annotations"]
    assert MANIFEST_ANNOTATION in ann
    assert ann[VISIBILITY_ANNOTATION] == "public"


def test_push_private_marks_visibility(tmp_path: Path) -> None:
    store, fake = _store(tmp_path)
    store.push(_image(tmp_path, "secret", "1.0.0"), private=True)
    ann = fake.store["hub.locus.test/library/secret:1.0.0"]["annotations"]
    assert ann[VISIBILITY_ANNOTATION] == "private"


def test_push_pull_roundtrip(tmp_path: Path) -> None:
    store, _ = _store(tmp_path)
    store.push(_image(tmp_path, "doc-to-tables", "1.0.0"))
    pulled = store.pull("doc-to-tables:1.0.0")
    assert read_manifest(pulled).name == "doc-to-tables"
    # second pull is a cache hit
    assert store.cached("doc-to-tables:1.0.0") is not None


def test_pull_unknown_raises(tmp_path: Path) -> None:
    store, _ = _store(tmp_path)
    with pytest.raises(ImageNotFoundError):
        store.pull("ghost:1.0.0")


def test_version_resolution_latest(tmp_path: Path) -> None:
    store, _ = _store(tmp_path)
    store.push(_image(tmp_path, "img", "1.0.0"))
    store.push(_image(tmp_path, "img", "1.10.0"))
    store.push(_image(tmp_path, "img", "1.2.0"))
    assert store.resolve_version("img", None) == "1.10.0"


def test_inspect_reads_metadata_without_full_pull(tmp_path: Path) -> None:
    store, _ = _store(tmp_path)
    store.push(_image(tmp_path, "doc-to-tables", "1.0.0"))
    m = store.inspect("doc-to-tables:1.0.0")
    assert m.emits.tag() == "table/v1"


def test_inspect_private_hidden_when_unauthorized(tmp_path: Path) -> None:
    store, _ = _store(tmp_path)
    store.push(_image(tmp_path, "secret", "1.0.0"), private=True)
    with pytest.raises(ImageNotFoundError):
        store.inspect("secret:1.0.0", include_private=False)


def test_search_lists_tags_for_repo(tmp_path: Path) -> None:
    store, _ = _store(tmp_path)
    store.push(_image(tmp_path, "doc-to-tables", "1.0.0"))
    store.push(_image(tmp_path, "doc-to-tables", "1.1.0"))
    results = store.search("doc-to-tables")
    assert {s.version for s in results} == {"1.0.0", "1.1.0"}


def test_login_delegates_to_client(tmp_path: Path) -> None:
    store, fake = _store(tmp_path)
    store.login("user", "token")
    assert fake.logged_in is True
