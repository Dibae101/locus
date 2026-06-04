"""Resolved image abstraction (Layer 2, Stage 3.1).

A ``ResolvedImage`` binds an ``ImageManifest`` to a runnable capability: a callable
that consumes input artifacts + a stage context and produces an output DataFrame +
lineage, using the Layer 1 engine. Built-in images wrap the engine pipeline; the
``BuiltinDocToTables`` image is the reference capability that proves the runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import pandas as pd

from locus.artifacts import ArtifactType
from locus.manifest import ImageManifest


@dataclass
class StageContext:
    """Run context passed to a capability for one stage."""

    stage_id: str
    source: Any  # SourceSpec | None
    config: dict[str, Any] = field(default_factory=dict)
    credential_available: bool = False
    grounding_threshold: float = 0.7
    workspace_dir: str = "."


class Capability(Protocol):
    """The runnable behind an image."""

    def run(
        self, inputs: list[pd.DataFrame], ctx: StageContext
    ) -> tuple[pd.DataFrame, str]: ...
    # returns (result_frame_with_lineage_column, engine_mode)


@dataclass
class ResolvedImage:
    """An image ready to execute: manifest + capability."""

    manifest: ImageManifest
    capability: Capability

    @property
    def ref(self) -> str:
        return self.manifest.ref


def _builtin_manifest(name: str, accepts: list[ArtifactType], emits: ArtifactType) -> ImageManifest:
    return ImageManifest(
        name=name,
        version="0.1.0",
        accepts=accepts,
        emits=emits,
        engine_modes=["deterministic", "llm"],
        provenance_conformant=True,
        entrypoint=f"locus.image:{name}",
    )
