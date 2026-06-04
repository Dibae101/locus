"""Locusfile model (Layer 2, Stage 1.2).

The declarative run-configuration the consumer writes. Only a data source and an
image reference are required; everything else is optional with documented defaults
(Req 3.1). Supports a single-image shorthand and a multi-stage ``pipeline``.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SourceSpec(BaseModel):
    type: str  # "files" | "url" | "api" | "sql"
    path: str | None = None
    uri: str | None = None


class StageSpec(BaseModel):
    id: str
    image: str  # "name:version"
    needs: list[str] = Field(default_factory=list)  # dependency ids (Req 5.4)
    source: SourceSpec | None = None  # override the pipeline source
    config: dict[str, Any] = Field(default_factory=dict)


class PortSpec(BaseModel):
    ui: int | None = None
    api: int | None = None


class Locusfile(BaseModel):
    """The run-configuration surface (Req 3)."""

    image: str | None = None  # single-image shorthand
    source: SourceSpec | None = None
    pipeline: list[StageSpec] = Field(default_factory=list)
    volumes: list[str] = Field(default_factory=list)  # "host:container[:ro]" (Req 3.2)
    ports: PortSpec = Field(default_factory=PortSpec)  # (Req 3.3)
    schema_mode: str = "infer"  # (Req 3.4)
    schema_ref: str | None = None
    llm: dict[str, Any] | None = None  # (Req 3.5)
    env_file: str | None = None
    export: dict[str, Any] | None = None  # (Req 3.5)
    review: dict[str, Any] | None = None  # (Req 3.5)
    mode: str = "strict"  # "strict" | "permissive" (Req 7.7/7.8)

    def normalized_pipeline(self) -> list[StageSpec]:
        """Expand a single-image shorthand into a one-stage pipeline (Req 3.1)."""
        if self.pipeline:
            return self.pipeline
        if self.image:
            return [StageSpec(id="main", image=self.image)]
        return []
