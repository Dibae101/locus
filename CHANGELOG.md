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

## Layer 2 — Runtime (locus CLI)

### Added
- **CLI** (`locus`): `init`, `validate`, `run`, `build`, `push`, `pull`, `search`,
  `inspect`, `version` — Typer-based, single install.
- **Data models**: versioned `ArtifactType` (compatibility rules), `LocusArtifact`
  (path-based payload), `ImageManifest`, `Locusfile`.
- **Locusfile loading** with validation and credential safety (raw-key rejection,
  `.env` gitignore + git-tracked refusal).
- **Single-image run** via the in-process backend over the Layer 1 engine.
- **Multi-image composition**: `PipelinePlanner` (cycle detection, parallel waves,
  static artifact-type checking, conformance gating) + `StageExecutor` (dependency
  order, stage caching).
- **Cross-stage provenance**: terminal cells resolve to origin source locations across
  stages; permissive-mode lineage-breaking.
- **Distribution**: OCI-friendly image packaging; `LocalImageStore` (pull/cache/push/
  search/inspect, semantic version resolution, persisted public/private visibility).
- **Build + publish**: `ImageBuilder` pins versions and certifies provenance
  conformance; publish public/private.
- **Result serving**: local FastAPI preview UI (rows + per-cell faithfulness + source
  + flagged + engine mode) and export.
- **Backends**: default in-process; optional Docker backend (errors clearly when
  absent, no silent fallback).
- **Privacy disclosure**: per-image privacy class, consent before external-LLM egress,
  no blanket data-stays-local claim.
- **Hardening**: 8 runtime correctness properties in CI; 208 tests total.

### Notes
- The default image registry is a local filesystem store (`~/.locus/registry`); a real
  OCI/Harbor backend is interface-compatible future work.

## 0.0.7

### Fixed
- **Two-column PDF reading order.** Multi-column papers with a full-width
  title/abstract header (e.g. conference papers) were read straight across, zippering
  the left and right columns together and cutting sentences in half. The parser now
  detects a vertical whitespace *gutter* no word crosses, classifies each line as
  spanning (full-width) or column-bound, and emits the entire left column before the
  right — header first, then each column in natural reading order. Single-column
  documents are unaffected.
- **Empty results now explain themselves.** When a source can't be parsed into a table
  (e.g. an image that needs OCR), the extraction error is surfaced to the CLI (as a
  `warning:` line) and to the result UI (a "No rows were produced" notice naming the
  reason), instead of a silent blank page that looked identical for every failing file.

## 0.0.6

### Fixed
- **PDF text reconstruction.** The PDF parser dumped each whole page as a single
  "paragraph" using `extract_text()`, which (a) dropped inter-word spaces on PDFs that
  encode no space characters (`CloudPlatformandDevOps…`) and (b) read straight across
  multi-column layouts, interleaving columns into nonsense. Text is now rebuilt from
  positioned words: a font-size-derived word tolerance restores spacing, words are
  grouped into lines and lines into paragraphs on vertical gaps, and a strict
  empty-gutter test splits genuine two-column pages while leaving single-column
  documents (resumes, reports) in natural reading order. Each paragraph carries a
  bounding box enclosing its words.

## 0.0.5

### Added
- **Broad file-format support.** New dependency-free parsers (Python stdlib only) so a
  much wider range of files extract into tables:
  - **Markdown** (`.md`) — GitHub-style pipe tables become real tables; text otherwise.
  - **JSON** (`.json`) — arrays of objects → rows; nested objects → flattened
    key/value table (dotted/indexed paths). Also handles API/DB records.
  - **DOCX / PPTX / XLSX / ODT / EPUB** — these are ZIP+XML; tables and text are
    extracted directly via `zipfile` + `xml.etree`, no third-party libraries.
  - **Plain text** and common source/text files (`.txt`, `.css`, `.js`, `.py`, `.yaml`,
    `.xml`, `.svg`, `.drawio`, …) read as text.
  - **ZIP archives** (`.zip`) — contained files are parsed and merged, with provenance
    pointing at each member path.
  - **Images** (`.png`, `.jpg`, …) — clear, actionable "OCR required" error instead of
    a cryptic "no parser" failure.
- **Universal document-elements fallback.** When a document has text but no table grid
  (e.g. a resume PDF, a prose `.docx`), the deterministic engine now emits a structured
  `element | text | location` table — every cell grounded to its source location —
  instead of erroring. Any readable file produces a presentable, grounded table.

### Changed
- The legacy built-in `doc-to-tables` and the catalog image now share one multi-format
  parser registry, so both parse the same formats.

## 0.0.4

### Added
- **Declarative export.** The Locusfile `export` field is now a real feature, not just
  a CLI flag: `export.path`, `export.format` (csv | parquet | json | markdown, inferred
  from the path extension when omitted), and `export.include_lineage` (drop the per-cell
  `_lineage` column for a clean, human-facing table). The `--export` flag overrides
  `export.path` and a new `--format` flag overrides `export.format`. JSON and Markdown
  exporters added (Markdown is dependency-free).
- **`expose:` — web visualization, Dockerfile-style.** Add `expose: 8080` (or a full
  `{port, host, open}` mapping) to a Locusfile and `locus run` auto-serves an
  interactive view of the result: the table with per-cell provenance plus per-column
  profiles and charts (numeric histograms, categorical distributions, fill rate,
  cardinality). No spreadsheet needed. Binding to a non-loopback host prints an
  explicit no-auth warning. `--serve` forces it on; `--port` overrides the port.

### Changed
- The result preview UI now includes a **Visualize** section (CSS bar charts, no JS
  chart dependency) above the data/provenance table.

## 0.0.3

### Added
- **Convenience install bundles.** `pip install "locus-etl[standard]"` pulls the common
  document/format parsers + result UI (PDF, HTML, SQL, normalize, serve) without the
  heavy ML stacks; `pip install "locus-etl[all]"` installs every optional capability
  (adds OCR, LLM, embeddings, dedup, docling, docker, oci). The bare `locus-etl` stays
  lightweight — core CLI + engine + CSV/records + provenance. Install docs (README,
  Hub Getting Started) now explain the extras model and the shell-quoting requirement.

## 0.0.2

### Fixed
- **Missing `packaging` dependency** — `locus.store` imports `packaging.version` but it
  was not declared, breaking a clean install with `ModuleNotFoundError: No module named
  'packaging'` on `pull`/`search`. Added `packaging` (and confirmed `rapidfuzz`) to core
  dependencies. Verified every module imports and all CLI commands run in a clean venv.
- **Wrong package name in install hints** — optional-extra error messages told users to
  run `pip install locus-engine[...]` / `pip install locus[...]`. The published
  distribution is `locus-etl`, so those commands fail. Corrected all four hints (`pdf`,
  `llm`, `oci`, `serve`) to `pip install 'locus-etl[...]'` with shell-safe quotes.
- **Image build version pin** — `build_image` pinned `locus-engine`, which is not the
  installed distribution name, so the engine version was silently dropped from image
  manifests. Now pins `locus-etl`.
