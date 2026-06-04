"""Image packaging format (Layer 2, Stage 6/7).

A built Locus image is a directory/tarball containing a ``manifest.json`` (the
``ImageManifest``) plus the capability payload. This module defines the on-disk
format and (de)serialization. The format is intentionally OCI-friendly: the manifest
is a small JSON blob and the payload is a layer, so an OCI/ORAS backend can store it
as an artifact without changing the format.

Requirements: 9.1, 9.3.
"""

from __future__ import annotations

import json
import tarfile
import tempfile
from pathlib import Path

from locus.manifest import ImageManifest

MANIFEST_NAME = "manifest.json"
PAYLOAD_DIR = "payload"


def write_image_dir(target: Path, manifest: ImageManifest, payload_files: dict[str, bytes]) -> Path:
    """Write an unpacked image directory: manifest.json + payload/."""
    target.mkdir(parents=True, exist_ok=True)
    (target / MANIFEST_NAME).write_text(manifest.model_dump_json(indent=2))
    payload = target / PAYLOAD_DIR
    payload.mkdir(exist_ok=True)
    for rel, data in payload_files.items():
        p = payload / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return target


def read_manifest(image_dir: Path) -> ImageManifest:
    data = json.loads((image_dir / MANIFEST_NAME).read_text())
    return ImageManifest.model_validate(data)


def pack_image(image_dir: Path, archive_path: Path) -> Path:
    """Pack an unpacked image dir into a .tar.gz artifact."""
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(image_dir / MANIFEST_NAME, arcname=MANIFEST_NAME)
        payload = image_dir / PAYLOAD_DIR
        if payload.exists():
            tar.add(payload, arcname=PAYLOAD_DIR)
    return archive_path


def unpack_image(archive_path: Path, dest_dir: Path | None = None) -> Path:
    dest = dest_dir or Path(tempfile.mkdtemp(prefix="locus-img-"))
    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(dest, filter="data")
    return dest
