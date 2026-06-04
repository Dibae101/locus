# Implementation Plan

## Overview

Staged build plan for Layer 2 (the image runtime, packaging, distribution, registry). It depends on the implemented Layer 1 engine (`locus_engine`). Ordering: artifact/manifest models → Locusfile + single-image run → composition DAG + interchange → cross-stage provenance → distribution (pull/push/Hub) → build/publish → serve/export → hardening. Each task references the requirements it satisfies. LLM and network calls are mocked in unit tests.

Conventions: separate `locus` package (CLI) depending on `locus_engine`; Python 3.11+, uv, Pydantic v2, Typer, pytest.

## Tasks

### Stage 0 — Runtime package scaffold

- [x] 0.1 Create the `locus` package (CLI) depending on `locus_engine`
  - `pyproject.toml` for `locus`, Typer + Rich deps, optional extras (`docker`, `serve`, `oci`), dev tooling shared with the engine.
  - `LocusRuntimeError` hierarchy mirroring the engine's errors.
  - _Requirements: 1.1, 1.2_

### Stage 1 — Core runtime data models

- [x] 1.1 Implement `ArtifactType`, `ArtifactKind`, `Compat`, and `LocusArtifact`
  - Versioned type with `tag()` and `compatible_with()` (major/minor rules).
  - Unit tests for compatibility matrix (ok / minor-diff / incompatible).
  - _Requirements: 6.1, 6.2, 6.6_
- [x] 1.2 Implement `ImageManifest`, `StageSpec`, `SourceSpec`, `Locusfile`, `PortSpec`
  - Pydantic models with documented defaults; only source + image required.
  - _Requirements: 3.1, 9.2_

### Stage 2 — Locusfile loading and validation

- [x] 2.1 Implement `LocusfileLoader` (YAML load + model validation)
  - Single-image shorthand → one-stage pipeline; invalid setting → ConfigError.
  - _Requirements: 3.1, 3.6, 3.7_
- [x] 2.2 Implement credential safety checks
  - Reject raw key in Locusfile; resolve via engine `CredentialResolver`; `.env` gitignore on `init`; refuse git-tracked `.env`.
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

### Stage 3 — Single-image run (process backend)

- [x] 3.1 Implement `ProcessBackend` and `ResolvedImage`
  - Run an engine-backed capability in-process; produce a `LocusArtifact` (Arrow file) in the run workspace.
  - _Requirements: 1.3_
- [x] 3.2 Implement `Run_Workspace` and artifact (de)serialization
  - Write/read Arrow/Parquet payloads + lineage; content hashing for caching.
  - _Requirements: 6.2, 5.8_
- [x] 3.3 Wire `locus run` for a single image end-to-end
  - Locusfile → one stage → engine pipeline → artifact → (serve/export hook).
  - Golden test on a CSV using a stub image.
  - _Requirements: 1.3, 3.1_

### Stage 4 — Multi-image composition (DAG)

- [x] 4.1 Implement `PipelinePlanner`: graph build + cycle detection + waves
  - Topological ordering; parallelizable wave grouping; cycle → ConfigError.
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_
- [x] 4.2 Implement static interchange type-check across edges
  - Major mismatch fails; minor warns; runs before any stage executes.
  - _Requirements: 6.3, 6.4, 6.5, 6.6_
- [x] 4.3 Implement `StageExecutor` over the plan (process backend)
  - Execute waves; root stages get the pipeline source; dependents get upstream artifacts; terminal output = final result; stage caching.
  - _Requirements: 5.4, 5.7, 5.8_

### Stage 5 — Cross-stage provenance

- [x] 5.1 Implement `CrossStageProvenance` + run `Lineage_Store`
  - Thread engine lineage across stage boundaries; terminal cells resolve to origin.
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_
- [x] 5.2 Implement conformance gating per mode
  - Strict: non-conformant stage fails; permissive: continue + mark lineage-broken.
  - _Requirements: 7.7, 7.8_

### Stage 6 — Distribution (pull, cache, Hub)

- [x] 6.1 Implement `ImageStore.pull` + local cache (OCI/ORAS client)
  - Pull by name/version; cache hit reuse; pull-if-missing during run; not-found error; default version resolution.
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
- [x] 6.2 Implement `login` + `Registry_Credential` handling
  - Registry auth separate from LLM keys.
  - _Requirements: 10.1, 10.8_

### Stage 7 — Build and publish

- [x] 7.1 Implement `ImageBuilder` (manifest → BuiltImage, dep pinning, conformance cert)
  - Reuse engine conformance harness to set `provenance_conformant`.
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
- [x] 7.2 Implement `push` with public/private visibility + Hub metadata
  - Namespace authorization; private pull restriction; record types + conformance; self-hosted Hub path.
  - _Requirements: 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

### Stage 8 — Discovery

- [x] 8.1 Implement `search` + `inspect`
  - List images; report versions, accept/emit types, engine modes, privacy class, conformance; private only for authorized.
  - _Requirements: 11.1, 11.2, 11.3_

### Stage 9 — Serving, preview, export

- [x] 9.1 Implement `ResultServer` (FastAPI) on the mapped UI port
  - Rows + per-cell faithfulness + source location + flagged rows + engine mode; local only.
  - _Requirements: 8.1, 8.2, 8.3, 8.5_
- [x] 9.2 Implement `Exporter` for the configured format
  - _Requirements: 8.4_

### Stage 10 — Docker backend + privacy disclosure

- [x] 10.1 Implement `DockerBackend` (optional)
  - Run a stage in a container; clear error if Docker absent (no silent fallback).
  - _Requirements: 1.4, 1.5_
- [x] 10.2 Implement runtime privacy disclosure + consent
  - Classify image privacy class; consent before external-LLM egress; no blanket local claim.
  - _Requirements: 12.1, 12.2, 12.3_

### Stage 11 — Hardening and release-readiness

- [x] 11.1 Correctness-property suite (Properties 1-8) in CI
  - _Requirements: 5.6, 6.4, 7.x, 4.x, 10.8, 12.x_
- [x] 11.2 Golden two-stage pipeline integration test
  - _Requirements: 5.x, 6.x, 7.x_
- [x] 11.3 Coverage, typing, docs; CLI usage examples
  - _Requirements: 1.1_

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["0.1"], "depends_on": [] },
    { "wave": 2, "tasks": ["1.1", "1.2"], "depends_on": ["0.1"] },
    { "wave": 3, "tasks": ["2.1", "2.2"], "depends_on": ["1.1", "1.2"] },
    { "wave": 4, "tasks": ["3.1", "3.2", "3.3"], "depends_on": ["2.1", "2.2"] },
    { "wave": 5, "tasks": ["4.1", "4.2", "4.3"], "depends_on": ["3.1", "3.2", "3.3"] },
    { "wave": 6, "tasks": ["5.1", "5.2"], "depends_on": ["4.3"] },
    { "wave": 7, "tasks": ["6.1", "6.2", "7.1", "7.2", "8.1"], "depends_on": ["1.2"] },
    { "wave": 8, "tasks": ["9.1", "9.2"], "depends_on": ["3.3"] },
    { "wave": 9, "tasks": ["10.1", "10.2"], "depends_on": ["4.3"] },
    { "wave": 10, "tasks": ["11.1", "11.2", "11.3"], "depends_on": ["5.2", "6.1", "7.2", "8.1", "9.1", "9.2", "10.1", "10.2"] }
  ]
}
```

ASCII view:

```
Stage 0 (scaffold)
  └─> Stage 1 (artifact + manifest + locusfile models)
        ├─> Stage 2 (locusfile load + credential safety)
        │     └─> Stage 3 (single-image run, process backend)
        │           ├─> Stage 4 (composition DAG + interchange type-check)
        │           │     └─> Stage 5 (cross-stage provenance + conformance gating)
        │           ├─> Stage 9 (serve / preview / export)
        │           └─> Stage 10 (docker backend + privacy disclosure)
        └─> Stage 6/7/8 (distribution / build+publish / discovery)  [parallelizable]
                    └─> Stage 11 (hardening + release readiness)  [needs all]
```

## Notes

- **Engine reuse:** all data transformation and provenance logic comes from `locus_engine`; this layer orchestrates and must not duplicate it.
- **Artifacts pass by file** in the run workspace to enable the Docker backend, caching, and large data.
- **Static type-check + conformance gating happen before execution** — composition must fail fast, never produce corrupt output.
- **Registry-agnostic:** default hub is Harbor but the CLI speaks plain OCI; swappable via config.
- Build the single-image path (Stage 3) before composition (Stage 4); it is the smallest runnable product and the integration point for serving/export.
