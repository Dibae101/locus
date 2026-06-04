"""Image store: pull, cache, push, search (Layer 2, Stage 6).

Defines the ``ImageStore`` protocol and a ``LocalImageStore`` filesystem backend that
is fully functional offline. A future ``OrasImageStore`` implements the same protocol
against an OCI registry (Harbor); because the CLI depends only on the protocol, the
default backend is swappable via config without code changes.

Image references are ``name:version``; an omitted version resolves to the latest
available (Req 2.5).

Requirements: 2.1, 2.2, 2.4, 2.5, 10.2, 10.3, 10.4, 11.1.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from packaging.version import InvalidVersion, Version

from locus.errors import ImageNotFoundError
from locus.manifest import PrivacyClass
from locus.packaging import pack_image, read_manifest, unpack_image, write_image_dir


@dataclass
class ImageSummary:
    name: str
    version: str
    emits: str
    accepts: list[str]
    privacy_class: PrivacyClass
    provenance_conformant: bool
    private: bool = False


def split_ref(ref: str) -> tuple[str, str | None]:
    name, sep, version = ref.partition(":")
    return name, (version or None) if sep else None


def _latest(versions: list[str]) -> str | None:
    if not versions:
        return None
    try:
        return max(versions, key=Version)
    except InvalidVersion:
        return sorted(versions)[-1]


class ImageStore(Protocol):
    def pull(self, ref: str) -> Path: ...           # returns unpacked image dir
    def cached(self, ref: str) -> Path | None: ...
    def push(self, image_dir: Path, *, private: bool = False) -> str: ...
    def search(self, query: str = "") -> list[ImageSummary]: ...
    def resolve_version(self, name: str, version: str | None) -> str: ...


class LocalImageStore:
    """Filesystem-backed store. Layout: <root>/<name>/<version>/{manifest.json,payload/}."""

    def __init__(self, root: str | Path, cache_dir: str | Path | None = None) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._cache = Path(cache_dir) if cache_dir else self._root / ".cache"
        self._cache.mkdir(parents=True, exist_ok=True)
        self._private: set[str] = set()

    # --- version resolution ---------------------------------------------

    def _versions(self, name: str) -> list[str]:
        d = self._root / name
        if not d.exists():
            return []
        return [p.name for p in d.iterdir() if p.is_dir()]

    def resolve_version(self, name: str, version: str | None) -> str:
        if version is not None:
            return version
        latest = _latest(self._versions(name))
        if latest is None:
            raise ImageNotFoundError(name)
        return latest

    # --- pull / cache ----------------------------------------------------

    def cached(self, ref: str) -> Path | None:
        name, version = split_ref(ref)
        version = version or _latest(self._versions(name))
        if version is None:
            return None
        cached = self._cache / name / version
        return cached if (cached / "manifest.json").exists() else None

    def pull(self, ref: str) -> Path:
        name, requested = split_ref(ref)
        version = self.resolve_version(name, requested)
        src = self._root / name / version
        if not (src / "manifest.json").exists():
            raise ImageNotFoundError(f"{name}:{version}")
        dest = self._cache / name / version
        if (dest / "manifest.json").exists():
            return dest  # cache hit (Req 2.2)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest, dirs_exist_ok=True)
        return dest

    # --- push ------------------------------------------------------------

    def push(self, image_dir: Path, *, private: bool = False) -> str:
        manifest = read_manifest(image_dir)
        dest = self._root / manifest.name / manifest.version
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(image_dir, dest)
        # Persist visibility so it survives across CLI invocations (Req 10.4).
        (dest / ".private").write_text("1" if private else "0")
        if private:
            self._private.add(manifest.ref)
        return manifest.ref

    def _is_private(self, image_dir: Path, ref: str) -> bool:
        marker = image_dir / ".private"
        if marker.exists():
            return marker.read_text().strip() == "1"
        return ref in self._private

    # --- search ----------------------------------------------------------

    def search(self, query: str = "", *, include_private: bool = True) -> list[ImageSummary]:
        out: list[ImageSummary] = []
        for name_dir in sorted(self._root.iterdir()):
            if not name_dir.is_dir() or name_dir.name.startswith("."):
                continue
            if query and query.lower() not in name_dir.name.lower():
                continue
            for ver_dir in sorted(name_dir.iterdir()):
                if not (ver_dir / "manifest.json").exists():
                    continue
                m = read_manifest(ver_dir)
                is_private = self._is_private(ver_dir, m.ref)
                if is_private and not include_private:
                    continue
                out.append(
                    ImageSummary(
                        name=m.name,
                        version=m.version,
                        emits=m.emits.tag(),
                        accepts=[a.tag() for a in m.accepts],
                        privacy_class=m.privacy_class,
                        provenance_conformant=m.provenance_conformant,
                        private=is_private,
                    )
                )
        return out


# Re-export packaging helpers commonly used alongside the store.
__all__ = [
    "ImageStore",
    "LocalImageStore",
    "ImageSummary",
    "split_ref",
    "pack_image",
    "unpack_image",
    "write_image_dir",
    "read_manifest",
]
