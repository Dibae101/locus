"""Plugin interfaces and shared context types (Stage 2.1).

All extension points are ``runtime_checkable`` Protocols. A built-in or third-party
component is any object that structurally satisfies one of these. The
``PluginRegistry`` (Stage 2.2) validates method presence before registration.

Requirements: 10.1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from locus_engine.ir import IntermediateRepresentation
from locus_engine.table import Cell, ProvenancedTable

# --- shared value objects -------------------------------------------------


@dataclass(frozen=True)
class SourceRef:
    """A reference to an input source, before it is read."""

    uri: str  # path, URL, DSN, or API endpoint
    kind: str | None = None  # optional explicit kind hint ("file", "url", "sql", "api")


@dataclass
class RawSource:
    """Raw content produced by a Connector (Req 1.3)."""

    source_id: str
    content_type: str
    data: bytes | None = None  # raw bytes for file/url/ocr
    records: list[dict[str, Any]] | None = None  # structured rows for api/db


@dataclass
class ResolvedSchema:
    """The target schema in one of three modes (Req 4.1)."""

    mode: str = "infer"  # "infer" | "hint" | "strict"
    columns: list[str] = field(default_factory=list)  # hint-mode column names
    hints: dict[str, Any] = field(default_factory=dict)  # hint-mode per-column guidance
    model: Any | None = None  # strict-mode Pydantic model class


@dataclass
class ExtractContext:
    """Run context handed to an extraction engine."""

    schema: ResolvedSchema
    credential_available: bool = False
    retry_limit: int = 2
    provider: str | None = None
    model: str | None = None


@dataclass
class ValidateContext:
    """Run context handed to a validator."""

    threshold: float = 0.7
    credential_available: bool = False


@dataclass
class EmitResult:
    """Outcome of an emit operation."""

    destination: str
    rows_written: int


# --- plugin protocols -----------------------------------------------------


@runtime_checkable
class Connector(Protocol):
    """Reads raw content from an input location (Req 1)."""

    name: str

    def supports(self, ref: SourceRef) -> bool: ...
    def read(self, ref: SourceRef) -> RawSource: ...


@runtime_checkable
class Parser(Protocol):
    """Converts a RawSource into the Intermediate Representation (Req 2, 3)."""

    name: str
    content_types: tuple[str, ...]

    def supports(self, content_type: str) -> bool: ...
    def parse(self, raw: RawSource) -> IntermediateRepresentation: ...


@runtime_checkable
class ExtractionEngine(Protocol):
    """Fills rows of a target schema from the IR (Req 4, 13, 14)."""

    name: str

    def extract(
        self,
        ir: IntermediateRepresentation,
        schema: ResolvedSchema,
        ctx: ExtractContext,
    ) -> ProvenancedTable: ...


@runtime_checkable
class Validator(Protocol):
    """Computes a faithfulness score for a cell against its source (Req 7)."""

    name: str

    def score(
        self,
        cell: Cell,
        ir: IntermediateRepresentation,
        ctx: ValidateContext,
    ) -> float: ...


@runtime_checkable
class Emitter(Protocol):
    """Writes a ProvenancedTable to a tabular output (Req 8)."""

    name: str
    fmt: str  # "dataframe" | "parquet" | "sql"

    def emit(self, table: ProvenancedTable, dest: str) -> EmitResult: ...


# Required method names per protocol, used by the registry's validation (Req 10.3).
REQUIRED_METHODS: dict[type, tuple[str, ...]] = {
    Connector: ("supports", "read"),
    Parser: ("supports", "parse"),
    ExtractionEngine: ("extract",),
    Validator: ("score",),
    Emitter: ("emit",),
}
