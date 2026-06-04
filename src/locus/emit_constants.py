"""Shared emit constants for the runtime.

Re-exports the engine's lineage column name so the runtime references a single
source of truth without reaching into engine internals at call sites.
"""

from __future__ import annotations

from locus_engine.emit.common import LINEAGE_COLUMN

__all__ = ["LINEAGE_COLUMN"]
