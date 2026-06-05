"""Locusfile model (Layer 2, Stage 1.2).

The declarative run-configuration the consumer writes. Only a data source and an
image reference are required; everything else is optional with documented defaults
(Req 3.1). Supports a single-image shorthand and a multi-stage ``pipeline``.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


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


class ExportSpec(BaseModel):
    """Declarative output: where and in what format to write the result.

    ``format`` is optional; when omitted it is inferred from the ``path`` extension
    (``.csv`` / ``.parquet`` / ``.json`` / ``.md``), defaulting to CSV. The CLI
    ``--export`` flag overrides ``path`` when supplied.

    ``include_lineage`` controls whether the per-cell ``_lineage`` provenance column
    is written. It defaults to True (provenance is Locus's point); set it False for a
    clean, human-facing table.
    """

    path: str | None = None
    format: str | None = None  # csv | parquet | json | markdown
    include_lineage: bool = True


class ExposeSpec(BaseModel):
    """Declarative web visualization, like a Dockerfile ``EXPOSE``.

    When set, ``locus run`` serves an interactive view of the result (table + column
    profiles + charts) on a local port instead of requiring the user to open the data
    in a spreadsheet. Use the ``expose: 8080`` integer shorthand or the full form::

        expose:
          port: 8080
          host: 127.0.0.1   # 0.0.0.0 to expose beyond localhost
          open: true        # auto-open the browser

    ``host`` defaults to loopback for safety; the run prints a warning if bound to a
    non-loopback address since the result is served without authentication.
    """

    port: int = 8080
    host: str = "127.0.0.1"
    open: bool = False

    @classmethod
    def coerce(cls, value: Any) -> ExposeSpec | None:
        """Accept the ``expose: 8080`` int shorthand or a full mapping."""
        if value is None:
            return None
        if isinstance(value, bool):  # avoid bool-is-int surprise
            return cls() if value else None
        if isinstance(value, int):
            return cls(port=value)
        if isinstance(value, ExposeSpec):
            return value
        if isinstance(value, dict):
            return cls.model_validate(value)
        raise ValueError("expose must be a port number or a mapping with a 'port'")


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
    export: ExportSpec | None = None  # (Req 3.5)
    expose: ExposeSpec | None = None  # auto-serve a visualization (Dockerfile-style)
    review: dict[str, Any] | None = None  # (Req 3.5)
    mode: str = "strict"  # "strict" | "permissive" (Req 7.7/7.8)

    @field_validator("expose", mode="before")
    @classmethod
    def _coerce_expose(cls, value: Any) -> ExposeSpec | None:
        return ExposeSpec.coerce(value)

    def normalized_pipeline(self) -> list[StageSpec]:
        """Expand a single-image shorthand into a one-stage pipeline (Req 3.1)."""
        if self.pipeline:
            return self.pipeline
        if self.image:
            return [StageSpec(id="main", image=self.image)]
        return []
