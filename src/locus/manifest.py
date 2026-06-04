"""Image manifest model (Layer 2, Stage 1.2).

The build-time declaration of an image: what it accepts/emits, which engine modes it
supports, its privacy class, and (set by build-time certification) whether it is
provenance-conformant.

Requirements: 9.2.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from locus.artifacts import ArtifactType


class PrivacyClass(StrEnum):
    LOCAL_ONLY = "local_only"
    CALLS_EXTERNAL = "calls_external"  # an LLM-backed image (Req 12.2)


class ImageManifest(BaseModel):
    """Declares an image's interface and properties (Req 9.2)."""

    name: str
    version: str
    description: str = ""
    accepts: list[ArtifactType] = Field(default_factory=list)
    emits: ArtifactType
    engine_modes: list[str] = Field(default_factory=lambda: ["deterministic"])
    privacy_class: PrivacyClass = PrivacyClass.LOCAL_ONLY
    provenance_conformant: bool = False  # set by build certification (Req 9.4)
    entrypoint: str = ""  # import path of the capability callable
    dependencies: dict[str, str] = Field(default_factory=dict)  # pinned (Req 9.3)

    @property
    def ref(self) -> str:
        return f"{self.name}:{self.version}"
