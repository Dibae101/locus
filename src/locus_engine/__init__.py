"""Locus engine — Layer 1.

Turns an unstructured corpus into validated, source-grounded tabular data.
The public API is intentionally small and grows as stages land.
"""

from __future__ import annotations

from locus_engine.composer import ProvenanceComposer
from locus_engine.config import (
    DedupConfig,
    LLMConfig,
    PipelineConfig,
    SourceConfig,
)
from locus_engine.ir import (
    IR_SCHEMA_VERSION,
    IntermediateRepresentation,
    IRElement,
    IRElementKind,
    IRTable,
)
from locus_engine.lineage import InMemoryLineageStore, LineageStore
from locus_engine.observability import (
    ObservabilityBus,
    ObservabilityEvent,
    Severity,
)
from locus_engine.plugins import (
    Connector,
    EmitResult,
    Emitter,
    ExtractContext,
    ExtractionEngine,
    Parser,
    RawSource,
    ResolvedSchema,
    SourceRef,
    ValidateContext,
    Validator,
)
from locus_engine.provenance import (
    BBox,
    CharSpan,
    GroundingMode,
    LineageEdge,
    OpKind,
    Provenance,
    SourceLocation,
    new_id,
)
from locus_engine.registry import PluginRegistry
from locus_engine.results import Outcome, RunResult, SourceOutcome
from locus_engine.table import (
    TABLE_SCHEMA_VERSION,
    Cell,
    ProvenancedTable,
    Row,
)

__version__ = "0.0.1"

__all__ = [
    "__version__",
    # provenance
    "BBox",
    "CharSpan",
    "SourceLocation",
    "GroundingMode",
    "OpKind",
    "LineageEdge",
    "Provenance",
    "new_id",
    # table
    "Cell",
    "Row",
    "ProvenancedTable",
    "TABLE_SCHEMA_VERSION",
    # composer
    "ProvenanceComposer",
    # ir
    "IntermediateRepresentation",
    "IRElement",
    "IRElementKind",
    "IRTable",
    "IR_SCHEMA_VERSION",
    # lineage
    "LineageStore",
    "InMemoryLineageStore",
    # plugins
    "Connector",
    "Parser",
    "ExtractionEngine",
    "Validator",
    "Emitter",
    "SourceRef",
    "RawSource",
    "ResolvedSchema",
    "ExtractContext",
    "ValidateContext",
    "EmitResult",
    # registry
    "PluginRegistry",
    # config
    "PipelineConfig",
    "SourceConfig",
    "LLMConfig",
    "DedupConfig",
    # observability
    "ObservabilityBus",
    "ObservabilityEvent",
    "Severity",
    # results
    "RunResult",
    "SourceOutcome",
    "Outcome",
]
