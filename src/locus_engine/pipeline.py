"""Pipeline orchestrator (Stage 3.6) — deterministic path.

Runs the ordered phases Ingest -> Parse -> Extract -> Validate -> Emit for a corpus,
isolating per-source failures (one bad source records an error and the run continues)
and emitting observability events. Config is validated before any source is processed.

Requirements: 12.4; 11.x; Property 8 (per-source isolation).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from locus_engine.config import PipelineConfig
from locus_engine.emit.dataframe import DataFrameEmitter
from locus_engine.errors import LocusError, ParserUnavailableError, SourceError
from locus_engine.extract.deterministic import DeterministicEngine
from locus_engine.ir import IntermediateRepresentation
from locus_engine.lineage import InMemoryLineageStore
from locus_engine.observability import ObservabilityBus
from locus_engine.parsers.router import ParserRouter
from locus_engine.plugins import ExtractContext, ResolvedSchema, SourceRef
from locus_engine.registry import PluginRegistry
from locus_engine.results import Outcome, RunResult, SourceOutcome
from locus_engine.table import ProvenancedTable, Row
from locus_engine.validate.grounding import GroundingValidator


@dataclass
class PipelineOutput:
    """The result of a pipeline run: the final table plus the run summary."""

    table: ProvenancedTable
    result: RunResult
    lineage: InMemoryLineageStore = field(default_factory=InMemoryLineageStore)


class Pipeline:
    """Deterministic-path orchestrator for a corpus of sources."""

    def __init__(
        self,
        config: PipelineConfig,
        registry: PluginRegistry,
        *,
        observability: ObservabilityBus | None = None,
        schema: ResolvedSchema | None = None,
    ) -> None:
        self._config = config
        self._registry = registry
        self._obs = observability or ObservabilityBus()
        self._schema = schema or ResolvedSchema(mode=config.schema_mode)
        self._router = ParserRouter(registry, overrides=config.parser_overrides)
        self._engine = DeterministicEngine()
        self._validator = GroundingValidator()
        self._lineage = InMemoryLineageStore()

    def run(self, refs: list[SourceRef]) -> PipelineOutput:
        result = RunResult()
        all_rows: list[Row] = []
        columns: list[str] = []

        for ref in refs:
            try:
                table = self._process_source(ref)
            except ParserUnavailableError:
                # Run-fatal: do not continue (Req 2.4).
                raise
            except SourceError as exc:
                self._obs.error(exc.__class__.__name__, exc.reason, source_id=exc.source_id)
                result.record(
                    SourceOutcome(source_id=exc.source_id, outcome=Outcome.ERROR, reason=exc.reason)
                )
                continue
            except LocusError as exc:  # pragma: no cover - defensive
                self._obs.error("pipeline", str(exc), source_id=ref.uri)
                result.record(
                    SourceOutcome(source_id=ref.uri, outcome=Outcome.ERROR, reason=str(exc))
                )
                continue

            if not columns:
                columns = table.columns
            all_rows.extend(table.rows)
            result.record(SourceOutcome(source_id=table.rows[0].source_id or ref.uri,
                                        outcome=Outcome.SUCCESS)
                          if table.rows else
                          SourceOutcome(source_id=ref.uri, outcome=Outcome.SUCCESS))

        final = ProvenancedTable(columns=columns, rows=all_rows, produced_by_engine="deterministic")
        flagged = sum(1 for r in final.rows if r.flagged)
        result.rows_emitted = len(final.rows)
        result.rows_flagged = flagged
        self._obs.corpus_summary(
            sources_processed=result.sources_processed,
            rows_emitted=result.rows_emitted,
            rows_flagged=result.rows_flagged,
            rows_rejected=result.rows_rejected,
            success=result.corpus_success,
        )
        return PipelineOutput(table=final, result=result, lineage=self._lineage)

    def _process_source(self, ref: SourceRef) -> ProvenancedTable:
        # Ingest
        with self._obs.phase("ingest", source_id=ref.uri):
            connector = self._registry.connector_for(ref)
            raw = connector.read(ref)

        # Parse
        with self._obs.phase("parse", source_id=raw.source_id):
            parser = self._router.route(raw)
            ir: IntermediateRepresentation = parser.parse(raw)

        # Extract
        with self._obs.phase("extract", source_id=raw.source_id):
            ctx = ExtractContext(
                schema=self._schema,
                credential_available=False,
                retry_limit=self._config.retry_limit,
            )
            table = self._engine.extract(ir, self._schema, ctx)
            for row in table.rows:
                self._lineage.put_all(list(row.cells.values()))

        # Validate (degraded grounding)
        with self._obs.phase("validate", source_id=raw.source_id):
            table = self._validator.validate(
                table,
                ir,
                threshold=self._config.grounding_threshold,
                rejection_mode=self._config.rejection_mode,
            )
        return table

    def emit(self, output: PipelineOutput) -> object:
        """Convenience: emit the final table via the default DataFrame emitter."""
        emitter = DataFrameEmitter()
        emitter.emit(output.table, dest="<dataframe>")
        return emitter.last_frame
