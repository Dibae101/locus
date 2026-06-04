# Changelog

All notable changes to the Locus engine (Layer 1) are documented here.

## [Unreleased]

Initial implementation of the Layer 1 processing engine, built stage by stage.

### Added
- **Core data model & provenance** — `Cell`/`Row`/`ProvenancedTable` (`table/v1`),
  `Provenance`, `SourceLocation`, and the `ProvenanceComposer` (map/merge/split/mask
  composition rules). Provenance is framework-managed and composes across transforms.
- **Intermediate Representation** (`ir/v1`) preserving text, tables, and source
  locations, plus an in-memory `LineageStore` with cycle-safe origin resolution.
- **Plugin framework** — `Connector`/`Parser`/`ExtractionEngine`/`Validator`/`Emitter`
  protocols, a validating `PluginRegistry`, `PipelineConfig`, and an `ObservabilityBus`.
- **Deterministic vertical slice** — `FileConnector`, `CsvParser` + `ParserRouter`,
  `DeterministicEngine`, degraded-mode `GroundingValidator`, `DataFrameEmitter`/
  `ParquetEmitter`, and the `Pipeline` orchestrator with per-source isolation.
- **Provenance conformance harness** — reusable assertions certifying provenance
  survival and the composition invariants; runs against built-in components.
- **Cleaning, normalization, deduplication** — `Cleaner` (type coercion + rules) and
  `Deduplicator` (rapidfuzz blocking + provenance-retaining merge).
- **Opt-in LLM engine** — local-only `CredentialResolver`, in-process LiteLLM
  `ProviderRouter`, guardrailed `LLMEngine` (bounded field-mapping), and a
  deterministic-first dual-engine reconciler. Full-mode (LLM-as-judge) grounding.
  Consent notice before any data leaves; no egress without a credential.
- **Schema inference** heuristics for infer mode; hint and strict modes.
- **Human-in-the-loop review** API — review queue, corrections with feedback records,
  approval, and feedback-to-prompt context.
- **More connectors/parsers/emitters** — HTTP/REST/SQL connectors, HTML and records
  parsers, SQL emitter.
- **Hardening** — consolidated correctness-property suite (9 properties), CI workflow
  (ruff + mypy + pytest on Python 3.11/3.12), 94% test coverage.

### Notes
- Default engine is deterministic and fully local; the LLM engine activates only when
  a local credential is present.
- Heavy/native dependencies (Docling, OCR, Splink, libpostal) are optional extras to
  keep the core lightweight.
