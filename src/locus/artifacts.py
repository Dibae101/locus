"""Stage interchange artifact types (Layer 2, Stage 1.1).

A ``LocusArtifact`` is the only structure that crosses a stage boundary. Its
``ArtifactType`` is versioned; compatibility across a stage edge follows the rule:
same kind + same major = compatible (minor differences warn).

Requirements: 6.1, 6.2, 6.6.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ArtifactKind(StrEnum):
    IR = "ir"
    TABLE = "table"
    CHUNKS = "chunks"
    EMBEDDINGS = "embeddings"
    GRAPH = "graph"


class Compat(StrEnum):
    OK = "ok"
    MINOR_DIFF = "minor_diff"  # compatible with a warning (Req 6.6)
    INCOMPATIBLE = "incompatible"


class ArtifactType(BaseModel):
    """A versioned artifact type, e.g. kind=table major=1 -> tag 'table/v1'."""

    kind: ArtifactKind
    major: int = 1
    minor: int = 0

    def tag(self) -> str:
        return f"{self.kind.value}/v{self.major}"

    def compatible_with(self, consumer: ArtifactType) -> Compat:
        """Compatibility of THIS (producer's emitted type) with a consumer's accepted type."""
        if self.kind != consumer.kind or self.major != consumer.major:
            return Compat.INCOMPATIBLE
        if self.minor != consumer.minor:
            return Compat.MINOR_DIFF
        return Compat.OK

    @classmethod
    def parse(cls, text: str) -> ArtifactType:
        """Parse a tag like 'table/v1' or 'table/v1.2'."""
        kind_part, _, ver = text.partition("/")
        kind = ArtifactKind(kind_part)
        if not ver:
            return cls(kind=kind)
        ver = ver.lstrip("v")
        major_s, _, minor_s = ver.partition(".")
        return cls(kind=kind, major=int(major_s), minor=int(minor_s) if minor_s else 0)


class LocusArtifact(BaseModel):
    """The unit that crosses a stage boundary (Req 6.1).

    The payload lives as an Arrow/Parquet file in the run workspace (Req 6.2); the
    artifact carries only the path + metadata so it works across process/Docker
    backends and supports content-addressed stage caching.
    """

    type: ArtifactType
    payload_path: str
    lineage_path: str | None = None
    produced_by: str  # stage id
    engine_mode: str = "deterministic"  # "deterministic" | "llm"
