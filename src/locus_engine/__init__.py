"""Locus engine — Layer 1.

Turns an unstructured corpus into validated, source-grounded tabular data.
The public API is intentionally small and grows as stages land.
"""

from __future__ import annotations

from locus_engine.composer import ProvenanceComposer
from locus_engine.ir import (
    IR_SCHEMA_VERSION,
    IntermediateRepresentation,
    IRElement,
    IRElementKind,
    IRTable,
)
from locus_engine.lineage import InMemoryLineageStore, LineageStore
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
    # results
    "RunResult",
    "SourceOutcome",
    "Outcome",
]
