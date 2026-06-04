"""Pipeline configuration (Stage 2.3).

A Pydantic v2 model validated before any source is processed (Req 12.4). Applies
documented defaults (Req 12.2) and raises ``ConfigError`` with the offending setting
and permitted range on invalid values (Req 12.3). Only the data source is required
(Req 12.5).

Requirements: 12.1, 12.2, 12.3, 12.4, 12.5.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from locus_engine.errors import ConfigError

SchemaMode = Literal["infer", "hint", "strict"]
RejectionMode = Literal["flag", "reject", "retain"]
OutputFormat = Literal["dataframe", "parquet", "sql"]


class SourceConfig(BaseModel):
    type: str  # "files" | "url" | "api" | "sql"
    path: str | None = None
    uri: str | None = None


class LLMConfig(BaseModel):
    provider: str | None = None
    model: str | None = None


class DedupConfig(BaseModel):
    enabled: bool = False
    keys: list[str] = Field(default_factory=list)
    strategy: str = "first"


class PipelineConfig(BaseModel):
    """Run configuration. The engine-facing subset of the Locusfile surface."""

    source: SourceConfig
    schema_mode: SchemaMode = "infer"
    schema_ref: str | None = None
    llm: LLMConfig | None = None
    retry_limit: int = Field(default=2, ge=0)
    grounding_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    rejection_mode: RejectionMode = "flag"
    dedup: DedupConfig = Field(default_factory=DedupConfig)
    output_format: OutputFormat = "dataframe"
    parser_overrides: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def load(cls, data: dict[str, object]) -> PipelineConfig:
        """Validate a raw config dict, translating pydantic errors to ConfigError
        with the offending setting and permitted range (Req 12.3, 12.4)."""
        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            first = exc.errors()[0]
            loc = ".".join(str(p) for p in first["loc"])
            raise ConfigError(f"invalid setting {loc!r}: {first['msg']}") from exc
