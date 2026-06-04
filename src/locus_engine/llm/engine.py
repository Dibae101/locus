"""LLM extraction engine (Stage 6.3) — bounded, guardrailed field-mapping.

The LLM is restricted to the fuzzy task of mapping already-extracted content to
schema fields (Req 14.2). Its output is constrained to the schema and retried on a
violation up to the configured limit (Req 14.3). The LLM never performs structural
work and never makes unconstrained decisions.

The actual model call is injected as a ``field_mapper`` callable so the engine is
fully testable without a network. In production the mapper wraps Instructor over the
ProviderRouter; that wiring lives in ``llm_mapper.py`` (added with full-mode work).

Requirements: 4.3, 14.2, 14.3.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from locus_engine.errors import ExtractionError
from locus_engine.plugins import ExtractContext, ResolvedSchema
from locus_engine.table import ProvenancedTable

# A field mapper proposes {column: value} for one row's raw values, constrained to
# the schema. It raises ValueError on an unrecoverable schema violation.
FieldMapper = Callable[[dict[str, Any], ResolvedSchema], dict[str, Any]]


class LLMEngine:
    """Guardrailed LLM field-mapping engine. Off unless a mapper is supplied."""

    name = "llm"

    def __init__(self, field_mapper: FieldMapper) -> None:
        self._mapper = field_mapper

    def map_fields(
        self,
        det_table: ProvenancedTable,
        schema: ResolvedSchema,
        ctx: ExtractContext,
    ) -> ProvenancedTable:
        """Run the bounded mapper over each row, enforcing schema with retry.

        Returns a NEW table whose values are the mapper's proposals. Provenance from
        the deterministic table is carried by the reconciler (engine.py is bounded to
        producing proposals; reconciliation happens in the Extractor, Stage 6.4)."""
        mapped_rows = []
        for row in det_table.rows:
            raw_values = row.value_dict()
            proposal = self._map_with_retry(raw_values, schema, ctx)
            mapped_rows.append(proposal)
        # Return proposals attached to a shallow copy for the reconciler to use.
        result = det_table.model_copy(deep=True)
        result.produced_by_engine = "llm"
        for row, proposal in zip(result.rows, mapped_rows, strict=True):
            for col, value in proposal.items():
                if col in row.cells:
                    row.cells[col].value = value
        return result

    def _map_with_retry(
        self, raw: dict[str, Any], schema: ResolvedSchema, ctx: ExtractContext
    ) -> dict[str, Any]:
        attempts = 1 + max(0, ctx.retry_limit)
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                proposal = self._mapper(raw, schema)
                self._enforce_schema(proposal, schema)
                return proposal
            except (ValueError, TypeError) as exc:
                last_error = exc
        raise ExtractionError(
            "<llm>", f"schema-constrained mapping failed after retries: {last_error}"
        )

    @staticmethod
    def _enforce_schema(proposal: dict[str, Any], schema: ResolvedSchema) -> None:
        if schema.mode == "strict" and schema.model is not None:
            schema.model.model_validate(proposal)
