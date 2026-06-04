"""Pipeline orchestrator (Stage 3.6) — deterministic path.

Runs the ordered phases Ingest -> Parse -> Extract -> Validate -> Emit for a corpus,
isolating per-source failures (one bad source records an error and the run continues)
and emitting observability events. Config is validated before any source is processed.

Requirements: 12.4; 11.x; Property 8 (per-source isolation).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from locus_engine.clean.cleaner import Cleaner
from locus_engine.clean.dedup import Deduplicator
from locus_engine.config import PipelineConfig
from locus_engine.emit.dataframe import DataFrameEmitter
from locus_engine.errors import LocusError, ParserUnavailableError, SourceError
from locus_engine.extract.deterministic import DeterministicEngine
from locus_engine.extract.dual import Extractor
from locus_engine.ir import IntermediateRepresentation
from locus_engine.lineage import InMemoryLineageStore
from locus_engine.llm.credentials import CredentialResolver
from locus_engine.observability import ObservabilityBus, ObservabilityEvent
from locus_engine.parsers.router import ParserRouter
from locus_engine.plugins import ExtractContext, ResolvedSchema, SourceRef
from locus_engine.registry import PluginRegistry
from locus_engine.results import Outcome, RunResult, SourceOutcome
from locus_engine.review import ReviewQueue
from locus_engine.table import ProvenancedTable, Row
from locus_engine.validate.grounding import GroundingValidator


@dataclass
class PipelineOutput:
    """The result of a pipeline run: the final table plus the run summary."""

    table: ProvenancedTable
    result: RunResult
    lineage: InMemoryLineageStore = field(default_factory=InMemoryLineageStore)
    review_queue: ReviewQueue = field(default_factory=ReviewQueue)


class Pipeline:
    """Deterministic-path orchestrator for a corpus of sources."""

    def __init__(
        self,
        config: PipelineConfig,
        registry: PluginRegistry,
        *,
        observability: ObservabilityBus | None = None,
        schema: ResolvedSchema | None = None,
        credential_resolver: CredentialResolver | None = None,
        llm_engine: object | None = None,
    ) -> None:
        self._config = config
        self._registry = registry
        self._obs = observability or ObservabilityBus()
        self._schema = schema or ResolvedSchema(mode=config.schema_mode)
        self._router = ParserRouter(registry, overrides=config.parser_overrides)
        self._extractor = Extractor(DeterministicEngine(), llm=llm_engine)  # type: ignore[arg-type]
        self._validator = GroundingValidator()
        self._cleaner = Cleaner()
        self._dedup = (
            Deduplicator(keys=config.dedup.keys, strategy=config.dedup.strategy)
            if config.dedup.enabled and config.dedup.keys
            else None
        )
        self._creds = credential_resolver
        self._provider = config.llm.provider if config.llm else None
        self._credential_available = self._detect_credential()
        self._consent_shown = False
        self._lineage = InMemoryLineageStore()
        self._review = ReviewQueue()

    def _detect_credential(self) -> bool:
        """Local presence check only — no network (Req 13.4)."""
        if self._creds is None or self._provider is None:
            return False
        return self._creds.is_available(self._provider)

    @staticmethod
    def _consent_event(provider: str) -> ObservabilityEvent:
        """Consent notice raised before any data leaves (Req 13.6)."""
        return ObservabilityEvent(
            phase="consent",
            outcome="llm_enabled",
            detail={
                "message": (
                    f"LLM engine active: data will be sent to provider {provider!r} "
                    "using your local credential."
                ),
                "provider": provider,
            },
        )

    @staticmethod
    def _llm_available_notice() -> ObservabilityEvent:
        """Discoverability notice when running deterministic-only (Req 13.5)."""
        return ObservabilityEvent(
            phase="notice",
            outcome="llm_available",
            detail={
                "message": (
                    "Running deterministic engine. Add an LLM API key (.env or env var) "
                    "to enable LLM-assisted extraction and full grounding."
                )
            },
        )

    def run(self, refs: list[SourceRef]) -> PipelineOutput:
        result = RunResult()
        all_rows: list[Row] = []
        columns: list[str] = []
        engine_kind = "deterministic"

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
            if table.produced_by_engine == "llm":
                engine_kind = "llm"
            all_rows.extend(table.rows)
            result.record(SourceOutcome(source_id=table.rows[0].source_id or ref.uri,
                                        outcome=Outcome.SUCCESS)
                          if table.rows else
                          SourceOutcome(source_id=ref.uri, outcome=Outcome.SUCCESS))

        final = ProvenancedTable(columns=columns, rows=all_rows, produced_by_engine=engine_kind)
        if self._dedup is not None:
            with self._obs.phase("dedup"):
                final = self._dedup.dedupe(final)
        flagged = sum(1 for r in final.rows if r.flagged)
        # Populate the review queue with flagged rows (Req 9.1).
        self._review.add_table_flagged(final.rows)
        result.rows_emitted = len(final.rows)
        result.rows_flagged = flagged
        self._obs.corpus_summary(
            sources_processed=result.sources_processed,
            rows_emitted=result.rows_emitted,
            rows_flagged=result.rows_flagged,
            rows_rejected=result.rows_rejected,
            success=result.corpus_success,
        )
        return PipelineOutput(
            table=final,
            result=result,
            lineage=self._lineage,
            review_queue=self._review,
        )

    def _process_source(self, ref: SourceRef) -> ProvenancedTable:
        # Ingest
        with self._obs.phase("ingest", source_id=ref.uri):
            connector = self._registry.connector_for(ref)
            raw = connector.read(ref)

        # Parse
        with self._obs.phase("parse", source_id=raw.source_id):
            parser = self._router.route(raw)
            ir: IntermediateRepresentation = parser.parse(raw)

        # Extract (deterministic-first; LLM opt-in if a credential is present)
        with self._obs.phase("extract", source_id=raw.source_id):
            if self._credential_available and not self._consent_shown:
                # Consent notice before the first byte leaves (Req 13.6).
                self._obs.emit(
                    self._consent_event(self._provider or "unknown")
                )
                self._consent_shown = True
            elif not self._credential_available:
                self._obs.emit(self._llm_available_notice())
            ctx = ExtractContext(
                schema=self._schema,
                credential_available=self._credential_available,
                retry_limit=self._config.retry_limit,
                provider=self._provider,
                model=self._config.llm.model if self._config.llm else None,
            )
            table = self._extractor.extract(ir, self._schema, ctx)

        # Clean (type coercion + normalization)
        with self._obs.phase("clean", source_id=raw.source_id):
            # In infer mode, use the engine's inferred column types for coercion.
            cleaner = self._cleaner
            if table.inferred_types:
                cleaner = Cleaner(column_types=table.inferred_types)
            table, clean_errors = cleaner.clean(table)
            for msg in clean_errors:
                self._obs.error("clean", msg, source_id=raw.source_id)
            for row in table.rows:
                self._lineage.put_all(list(row.cells.values()))

        # Validate (grounding: full mode if LLM active, else degraded)
        with self._obs.phase("validate", source_id=raw.source_id):
            table = self._validator.validate(
                table,
                ir,
                threshold=self._config.grounding_threshold,
                rejection_mode=self._config.rejection_mode,
                use_full_mode=self._credential_available,
            )
        return table

    def emit(self, output: PipelineOutput) -> object:
        """Convenience: emit the final table via the default DataFrame emitter."""
        emitter = DataFrameEmitter()
        emitter.emit(output.table, dest="<dataframe>")
        return emitter.last_frame
