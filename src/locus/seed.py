"""Seed the catalog into a registry (Layer 2).

Builds every image in the curated catalog into a publishable image directory and
pushes it to the target ``ImageStore`` (local by default, or an OCI registry when
configured). This is how the official catalog is populated so users can ``locus pull``
the images and run them.

Each seeded image embeds its manifest (with conformance + privacy metadata) and a
small payload recording the catalog entrypoint, so it round-trips through the store.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from locus.catalog import CATALOG, all_images
from locus.packaging import write_image_dir

if TYPE_CHECKING:
    from locus.store import ImageStore


def seed_catalog(store: ImageStore) -> list[str]:
    """Build and push every catalog image. Returns the list of pushed refs."""
    pushed: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for image in all_images():
            manifest = image.manifest
            image_dir = write_image_dir(
                Path(tmp) / manifest.ref.replace(":", "-"),
                manifest,
                {
                    "entrypoint.txt": f"locus.catalog:{manifest.name}".encode(),
                    "README.md": _readme(manifest).encode(),
                },
            )
            ref = store.push(image_dir, private=False)
            pushed.append(ref)
    return pushed


def _readme(manifest) -> str:  # type: ignore[no-untyped-def]
    accepts = ", ".join(a.tag() for a in manifest.accepts) or "(source)"
    return (
        f"# {manifest.name}\n\n{manifest.description}\n\n"
        f"- accepts: {accepts}\n- emits: {manifest.emits.tag()}\n"
        f"- engine modes: {', '.join(manifest.engine_modes)}\n"
        f"- privacy: {manifest.privacy_class.value}\n"
    )


def catalog_names() -> list[str]:
    return sorted(CATALOG)
