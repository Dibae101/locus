"""Shared helpers for catalog images."""

from __future__ import annotations

import pandas as pd

from locus.artifacts import ArtifactKind, ArtifactType
from locus.emit_constants import LINEAGE_COLUMN
from locus.image import ResolvedImage
from locus.manifest import ImageManifest, PrivacyClass

CATALOG_VERSION = "0.1.0"


def manifest(
    name: str,
    *,
    description: str,
    accepts: list[ArtifactType] | None,
    emits: ArtifactType,
    privacy: PrivacyClass = PrivacyClass.LOCAL_ONLY,
    engine_modes: list[str] | None = None,
) -> ImageManifest:
    return ImageManifest(
        name=name,
        version=CATALOG_VERSION,
        description=description,
        accepts=accepts or [],
        emits=emits,
        engine_modes=engine_modes or ["deterministic", "llm"],
        privacy_class=privacy,
        provenance_conformant=True,
        entrypoint=f"locus.catalog:{name}",
    )


def table_type() -> ArtifactType:
    return ArtifactType(kind=ArtifactKind.TABLE)


def data_columns(frame: pd.DataFrame) -> list[str]:
    return [c for c in frame.columns if c != LINEAGE_COLUMN]


def transform_image(
    name: str,
    description: str,
    capability_cls: type,
    *,
    privacy: PrivacyClass = PrivacyClass.LOCAL_ONLY,
) -> ResolvedImage:
    """Build a table->table transform image."""
    t = table_type()
    return ResolvedImage(
        manifest=manifest(
            name, description=description, accepts=[t], emits=t, privacy=privacy
        ),
        capability=capability_cls(),
    )
