# Implementation Plan

## Overview

Staged, test-driven build plan for Layer 1 (the processing engine). Each task is incremental, references the requirements it satisfies, and builds on prior tasks. Ordering follows the locked strategy: **core data model first → thin vertical slice (`doc-to-tables`) end-to-end → widen**. Layer 2 (runtime/hub) is out of scope here.

Conventions: Python 3.11+, `uv` + `pyproject.toml`, Pydantic v2, pytest. LLM calls are mocked in all unit tests (no network).

## Tasks

### Stage 0 — Project scaffold

- [ ] 0.1 Initialize the package with `uv` and `pyproject.toml`
  - Create `pyproject.toml` (name `locus-engine`, Python ≥3.11), `src/locus_engine/` layout, `tests/`, ruff + mypy config, pytest config.
  - Add core deps: `pydantic>=2`, `pandas`, `pyarrow`. Add dev deps: `pytest`, `pytest-cov`, `ruff`, `mypy`.
  - _Requirements: tech baseline_

- [ ] 0.2 Define the typed error hierarchy and result types
  - Implement `LocusError` base and `ConnectorError`, `ParserError`, `ExtractionError`, `ConfigError`, `RegistrationError`, `EmitError`.
  - Implement `RunResult` and per-source outcome record skeletons.
  - _Requirements: Error Handling; 11.5_


### Stage 1 — Core data model and provenance (foundation; everything binds here)

- [ ] 1.1 Implement source-location and provenance models
  - `BBox`, `CharSpan`, `SourceLocation`, `GroundingMode`, `OpKind`, `LineageEdge`, `Provenance` as Pydantic v2 models.
  - Unit tests: faithfulness range `[0,1]` enforced; default factories; serialization round-trip.
  - _Requirements: 3.3, 3.4, 7.2, 7.5_

- [ ] 1.2 Implement `Cell`, `Row`, `ProvenancedTable`
  - Stable `cell_id`/`row_id`; `value_dict()`; `schema_version="table/v1"`; `produced_by_engine` field.
  - Unit tests: construction, column keying, version constant.
  - _Requirements: 4.7, 8.4, 8.6; Property 9_

- [ ] 1.3 Implement `ProvenanceComposer` (map / merge / split / mask)
  - Implement the four composition rules exactly per the design table (map carries + marks re-grounding on value change; merge unions locations + min faithfulness; split carries to each child; mask preserves faithfulness).
  - Unit tests for each `OpKind`, including value-changed → `needs_regrounding=True` and merge location-union.
  - _Requirements: 5.4, 6.3, 7.10; Properties 3, 4, 5_

- [ ] 1.4 Implement `IntermediateRepresentation` (`ir/v1`)
  - `IRElementKind`, `IRTable`, `IRElement`, `IntermediateRepresentation` with `SourceLocation` on every element.
  - Unit tests: table preserved as row/col; version constant; every element located.
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 1.5 Implement in-memory `LineageStore`
  - `put`/`get`/`resolve_origins` (walk lineage edges back to `extract` origins).
  - Unit tests: multi-hop resolution (extract→map→merge) returns original source locations.
  - _Requirements: 7.10; Property 1_


### Stage 2 — Plugin framework and configuration

- [ ] 2.1 Define plugin Protocols
  - `Connector`, `Parser`, `ExtractionEngine`, `Validator`, `Emitter` as `runtime_checkable` Protocols with the designed signatures; shared `SourceRef`, `RawSource`, context dataclasses.
  - _Requirements: 10.1_

- [ ] 2.2 Implement `PluginRegistry` with registration validation
  - Validate method presence via Protocol check + `inspect.signature`; reject incomplete plugins with explicit missing-method list; config-named component overrides built-in.
  - Unit tests: register valid plugin; reject a deliberately incomplete plugin (Req 10.4); override precedence (Req 10.5).
  - _Requirements: 10.2, 10.3, 10.4, 10.5_

- [ ] 2.3 Implement `PipelineConfig` (Pydantic v2) and validation
  - All fields from the design with defaults; range validation; validate-before-run entry point.
  - Unit tests: defaults applied; out-of-range raises `ConfigError` naming setting+range; only source required.
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [ ] 2.4 Implement `ObservabilityBus` and `ObservabilityEvent`
  - Per-phase events (name, source_id, start, end, outcome); error events; corpus summary; configurable logging sink.
  - Unit tests: events emitted per phase; summary counts; corpus success with partial per-source errors.
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_


### Stage 3 — Vertical slice: `doc-to-tables` end-to-end (deterministic, no LLM)

Goal: smallest pipeline that proves the whole model — file → PDF parse → deterministic extract → degraded grounding → emit — with provenance intact end-to-end.

- [ ] 3.1 Implement `FileConnector`
  - Read local file paths; produce `RawSource` with unique `source_id` + detected content type.
  - Unit tests: reads a fixture file; unsupported source recorded + run continues.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ] 3.2 Implement `ParserRouter` + Docling-backed PDF parser
  - Content-type detection (extension + magic bytes + MIME); route with config override; halt on configured-but-unavailable parser.
  - Docling parser wrapper → emits `ir/v1` with `SourceLocation` (page + bbox where available). Docling models run locally (no LLM, no network).
  - Unit tests: routing, override, unavailable-halt (Req 2.4), unknown-type skip+continue; IR has located table cells. (Use a small committed PDF fixture.)
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 3.3 Implement `DeterministicEngine` extraction (infer + strict)
  - Derive rows from IR tables; infer mode (columns/types from IR) and strict mode (user Pydantic model with retry on validation failure); associate each cell with its `SourceLocation` via `extract` lineage.
  - Unit tests: infer produces a table; strict validates + retries to limit then records validation-failure error.
  - _Requirements: 4.1, 4.2, 4.4, 4.5, 4.6, 4.7_

- [ ] 3.4 Implement degraded-mode `GroundingValidator`
  - Score each cell by string/embedding similarity (rapidfuzz baseline; fastembed optional) between value and cited source span; set faithfulness + `grounding_mode=DEGRADED`; flag rows below threshold; reject/retain modes.
  - Unit tests: known supported vs unsupported values score as expected; threshold flagging; reject excludes + records, retain keeps + flags.
  - _Requirements: 7.1, 7.2, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 7.10_

- [ ] 3.5 Implement `DataFrameEmitter` and `ParquetEmitter` with lineage column
  - Output columns mirror schema + reserved `_lineage` column (locations + faithfulness); record producing engine; empty-output writes header/zero rows; write-error handling.
  - Unit tests: lineage column present and resolvable; empty result; inaccessible destination records `EmitError`.
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

- [ ] 3.6 Implement the `Pipeline` orchestrator (deterministic path) + per-source isolation
  - Wire phases Ingest→Parse→Extract→(Clean)→Validate→Emit; validate config first; per-source error isolation; corpus summary.
  - _Requirements: 12.4; 11.x; Property 8_

- [ ] 3.7 Golden end-to-end test for the vertical slice
  - Run the small PDF corpus through the full deterministic pipeline; assert emitted table, `_lineage` resolves to source locations, and corpus summary event.
  - _Requirements: Properties 1, 8, 9_


### Stage 4 — Provenance conformance harness (the critical guard)

- [ ] 4.1 Build the provenance-conformance test harness
  - Feed a known IR with seeded `SourceLocation`s through each built-in component; assert every output cell resolves through `LineageStore` to an original location; expose as a reusable `assert_provenance_conformant(component)` utility (reused by Layer 2 certification later).
  - _Requirements: Property 1; 7.10_

- [ ] 4.2 Add the cleaner/dedup conformance + correctness properties to the harness
  - Encode Properties 1–5 and 8 as automated checks runnable against any registered plugin.
  - _Requirements: Properties 1, 2, 3, 4, 5, 8_


### Stage 5 — Cleaning, normalization, deduplication

- [ ] 5.1 Implement `Cleaner` (type coercion + normalization)
  - Coerce to declared types; normalization helpers (dateparser, babel, phonenumbers, usaddress) behind a rule interface; preserve provenance via `map_cell`; coercion failure flags row + records error.
  - Unit tests: coercion, normalization rule application, failure flagging, provenance preserved.
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 5.2 Implement `Deduplicator` (rapidfuzz default)
  - Blocking by configured keys; rapidfuzz pair scoring; merge via `merge_cells` retaining all source locations; disabled = passthrough.
  - Unit tests: duplicates merged with retained lineage; disabled passthrough.
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ] 5.3 Add optional Splink and embedding entity-resolution plugins
  - Splink (DuckDB backend) and fastembed semantic matcher as optional, config-selected matchers behind the dedup interface.
  - Unit tests: plugin selection; semantic match catches a non-string-similar duplicate.
  - _Requirements: 6.1, 6.2; 10.x_


### Stage 6 — LLM engine (opt-in) with guardrails

- [ ] 6.1 Implement `CredentialResolver` (local-only)
  - Resolve key precedence `.env` → env var → OS keyring; presence-only check for activation; reject raw keys in config; never transmit.
  - Unit tests: precedence; raw-key-in-config rejected; presence check makes no network call.
  - _Requirements: 15.1, 15.2, 15.3; Property 7_

- [ ] 6.2 Implement `ProviderRouter` (in-process LiteLLM)
  - `complete(provider, model, messages, response_model)` → `litellm.completion("{provider}/{model}", ...)`; no proxy server.
  - Unit tests: provider/model string mapping; router is in-process (mock litellm).
  - _Requirements: 15.6, 15.7_

- [ ] 6.3 Implement `LLMEngine` (Instructor-wrapped, bounded to field-mapping)
  - Structured output enforced to schema with retry up to `retry_limit`; LLM restricted to fuzzy field-mapping only.
  - Unit tests (mocked LLM): schema-conformant output; retry on violation; LLM not invoked for structural work.
  - _Requirements: 4.3, 14.2, 14.3_

- [ ] 6.4 Implement dual-engine reconciliation in `Extractor`
  - Deterministic always first; activate LLM only on credential presence; reconcile so LLM cannot override a deterministic value without flagging the row.
  - Unit tests (engine parity): same fixture deterministic-only vs LLM; non-override-without-flag (Property 6); no-credential → deterministic path, no egress.
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 14.1, 14.4; Properties 6, 7_

- [ ] 6.5 Implement activation notices and consent
  - Discoverability notice when deterministic + no key; consent notice identifying provider before first byte leaves.
  - Unit tests: notice surfaced; consent fires before any provider call.
  - _Requirements: 13.5, 13.6_

- [ ] 6.6 Implement full-mode (LLM-as-judge) grounding
  - Add `GroundingMode.FULL` path to `GroundingValidator` using the constrained judge prompt; record mode.
  - Unit tests (mocked judge): full-mode score recorded with `grounding_mode=FULL`.
  - _Requirements: 7.3, 7.5, 14.5_


### Stage 7 — Schema modes completion and hint mode

- [ ] 7.1 Implement hint mode and schema inference heuristics
  - Hint mode (loose column guidance steers extraction without full validation); infer-mode heuristic layer (pandas/pyarrow type inference + header/units heuristics); optional LLM-assisted column naming when key present.
  - Unit tests: hint steering; infer heuristics on a headerless table.
  - _Requirements: 4.1, 4.2, 4.3_


### Stage 8 — Human-in-the-loop review (engine API)

- [ ] 8.1 Implement `ReviewQueue` and `Correction` recording
  - Flagged rows enter queue with provenance; correction updates cell via `OpKind.REVIEW` (reviewer id + timestamp); approved rows emitted without re-validation; feedback record links original/corrected/source.
  - Unit tests: queue population; correction recorded + provenance composed; approval bypasses re-validation.
  - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [ ] 8.2 Implement feedback-driven prompt refinement hook
  - When enabled, inject stored corrections into subsequent LLM extraction prompts.
  - Unit tests (mocked LLM): corrections appear in the next prompt context.
  - _Requirements: 9.5_


### Stage 9 — Remaining connectors, parsers, emitters

- [ ] 9.1 Implement `HttpConnector`, `RestApiConnector`, `SqlConnector`
  - Auth via config; per-source error isolation; unique source ids.
  - Unit tests: each connector reads a fixture/mock; auth passed via config (Req 1.6).
  - _Requirements: 1.1, 1.2, 1.3, 1.6_

- [ ] 9.2 Implement HTML parser (trafilatura + selectolax) and structured API/DB mapper
  - Emit `ir/v1` with locations (char_span for HTML).
  - Unit tests: HTML main-content + table extraction located; record mapper passthrough.
  - _Requirements: 2.2, 3.1, 3.2, 3.3_

- [ ] 9.3 Implement OCR parser (RapidOCR/Tesseract) for scanned PDFs/images
  - OCR with bbox → `SourceLocation`; route image-only sources here.
  - Unit tests (small image fixture): text extracted with bbox provenance.
  - _Requirements: 2.2, 3.3, 3.4_

- [ ] 9.4 Implement `SqlEmitter`
  - Write rows + `_lineage` to a SQL destination via SQLAlchemy; empty + write-error handling.
  - Unit tests: rows written to SQLite; empty/error cases.
  - _Requirements: 8.1, 8.2, 8.7_


### Stage 10 — Hardening and release-readiness

- [ ] 10.1 Full correctness-property suite green
  - Wire Properties 1–9 into CI; ensure conformance harness runs against all built-in plugins.
  - _Requirements: Properties 1–9_

- [ ] 10.2 Credential-safety and no-egress integration tests
  - End-to-end assert: no network egress without a credential; raw-key rejection; `.env` guardrails (engine-side portions).
  - _Requirements: 13.2, 15.2, 15.3; Property 7_

- [ ] 10.3 Coverage, typing, and docs
  - mypy clean; ruff clean; ≥ target coverage on core data model + composer + grounding; docstrings/usage examples for the public API.
  - _Requirements: tech baseline_

## Task Dependency Graph

Stages are mostly sequential; the dual-engine and later widening stages depend on the vertical slice and the data model. Independent stages that may proceed in parallel are grouped into waves below.

```json
{
  "waves": [
    { "wave": 1, "tasks": ["0.1", "0.2"], "depends_on": [] },
    { "wave": 2, "tasks": ["1.1", "1.2", "1.3", "1.4", "1.5"], "depends_on": ["0.1", "0.2"] },
    { "wave": 3, "tasks": ["2.1", "2.2", "2.3", "2.4"], "depends_on": ["1.1", "1.2", "1.3", "1.4", "1.5"] },
    { "wave": 4, "tasks": ["3.1", "3.2", "3.3", "3.4", "3.5", "3.6", "3.7"], "depends_on": ["2.1", "2.2", "2.3", "2.4"] },
    { "wave": 5, "tasks": ["4.1", "4.2"], "depends_on": ["3.7"] },
    { "wave": 6, "tasks": ["5.1", "5.2", "5.3", "6.1", "6.2", "6.3", "9.1", "9.2", "9.3", "9.4"], "depends_on": ["4.1", "4.2"] },
    { "wave": 7, "tasks": ["6.4", "6.5", "6.6", "8.1"], "depends_on": ["6.1", "6.2", "6.3"] },
    { "wave": 8, "tasks": ["7.1", "8.2"], "depends_on": ["6.4", "6.6", "8.1"] },
    { "wave": 9, "tasks": ["10.1", "10.2", "10.3"], "depends_on": ["5.1", "5.2", "5.3", "6.4", "6.5", "6.6", "7.1", "8.1", "8.2", "9.1", "9.2", "9.3", "9.4"] }
  ]
}
```

ASCII view of the same dependencies:

```
Stage 0 (scaffold)
  └─> Stage 1 (core data model + provenance)
        ├─> Stage 2 (plugin framework + config)
        └─> Stage 3 (vertical slice: doc-to-tables, deterministic)   [needs 1, 2]
              ├─> Stage 4 (provenance conformance harness)            [needs 1, 3]
              ├─> Stage 5 (clean / normalize / dedup)                 [needs 3, 4]
              ├─> Stage 6 (LLM engine opt-in + guardrails)            [needs 3]
              │     └─> Stage 7 (hint mode + schema inference)        [needs 6 for LLM-assisted infer]
              ├─> Stage 8 (human-in-the-loop review API)              [needs 3; 8.2 needs 6]
              └─> Stage 9 (more connectors / parsers / emitters)      [needs 2, 3]  (parallelizable)
                    └─> Stage 10 (hardening + release readiness)      [needs all]
```

Key edges:
- Everything depends on **Stage 1** (the data model is the foundation).
- **Stage 3** (vertical slice) is the first runnable product and the gate for all widening work.
- **Stage 4** (conformance harness) should land right after the slice so every later component is checked for provenance survival as it is built.
- **Stage 6** (LLM) is independent of Stages 5/8/9 and can be built in parallel once Stage 3 exists; tasks 7.1 (LLM-assisted infer), 8.2 (feedback prompts), and 6.6 (full-mode grounding) are the only cross-links into the LLM work.

## Notes

- **Build order rationale:** the vertical slice (Stage 3) deliberately uses the deterministic path only, so the entire pipeline shape and the provenance contract are proven before any LLM dependency is introduced. This is also the first `doc-to-tables` capability — the #1 catalog image.
- **Provenance is the priority invariant.** Stage 4's harness encodes Properties 1–5 and 8 and must run against every built-in plugin in CI; a component that drops lineage is a failing build, not a warning.
- **No network in unit tests.** All LLM/provider interactions are mocked. Property 7 (no-egress without credential) is asserted explicitly.
- **Lightweight-image constraint:** default deps stay small (Docling, pdfplumber, rapidfuzz, fastembed-optional). Heavy/native deps (libpostal, PaddleOCR, Splink) are optional extras, never required by the core.
- **Out of scope here:** CLI, Locusfile parsing, image packaging, Locus Hub, multi-image composition, and the serve/preview UI — all belong to the `locus-image-runtime` spec.
- Each `- [ ]` checkbox is a discrete, reviewable unit of work; complete and verify (tests green) before moving to the next within a stage.
