# Design Document

## Overview

This document specifies the design of **Layer 2 of Locus: the image runtime, packaging, distribution, and registry**. It builds on the Layer 1 engine (`unstructured-to-tabular-etl`, now implemented as the `locus_engine` package) and turns engine capabilities into reusable, versioned **images** that users pull, point at their own data via a **Locusfile**, run locally, preview, and export. Multiple images compose into a **pipeline DAG** with a versioned interchange contract and cross-stage provenance.

This layer is a separate installable package, `locus` (the CLI), which depends on `locus_engine`. The engine stays free of any packaging/registry concern; the runtime orchestrates engine-backed images.

### Tech baseline (inherited + additions)

- **Python 3.11+**, `uv` + `pyproject.toml`, Pydantic v2 (same as Layer 1).
- **CLI:** Typer (argument parsing, subcommands) + Rich (terminal output).
- **Registry transport:** ORAS-style OCI client (`oras` Python library) against Harbor; the CLI is registry-agnostic OCI so Harbor is swappable.
- **Artifact serialization:** Apache Arrow / Parquet for tabular payloads (already produced by the engine's emitters).
- **Result UI:** embedded FastAPI + a static front end, served locally via uvicorn.
- **Optional Docker backend:** the `docker` Python SDK, used only when `--runtime=docker`.

### Design principles

1. **The CLI is the only install.** A single `pip install locus`. No daemon, no Linux VM by default (Req 1).
2. **Local-first, registry-agnostic.** Runs on the user's machine; talks plain OCI so the default Harbor hub is swappable (architecture notes).
3. **Composition is a typed DAG, not docker-compose.** Compose-familiar YAML, pipeline execution semantics (Req 5).
4. **Trust is enforced at the seams.** Static type-check across stage edges before running (Req 6); provenance composes across stages or the build fails (Req 7).
5. **The engine does the work; the runtime orchestrates.** No data transformation logic lives here — it delegates to `locus_engine`.

## Architecture

```mermaid
flowchart TB
    subgraph cli["locus CLI (Typer)"]
        PULL[pull] 
        RUN[run]
        BUILD[build]
        PUSH[push]
        SEARCH[search]
        INIT[init]
    end

    subgraph rt["Runtime"]
        LF[LocusfileLoader\n+ validation]
        DAG[PipelinePlanner\nDAG + static type-check]
        EXEC[StageExecutor\nlocal-process | docker]
        PROV[CrossStageProvenance\n+ run LineageStore]
        WS[(Run_Workspace\nArrow artifacts)]
    end

    subgraph img["Image"]
        MAN[Image_Manifest\naccepts/emits, engine modes, privacy]
        CODE[engine-backed capability code]
    end

    subgraph dist["Distribution"]
        CACHE[(local image cache)]
        ORAS[OCI client / ORAS]
        HUB[(Locus Hub / Harbor)]
    end

    subgraph serve["Serving"]
        UI[Result UI\nFastAPI + static]
        EXP[Exporter]
    end

    ENG[[locus_engine\nLayer 1]]

    RUN --> LF --> DAG --> EXEC
    EXEC --> img
    img --> ENG
    EXEC <--> WS
    EXEC --> PROV
    PULL --> ORAS <--> HUB
    PULL --> CACHE
    BUILD --> MAN
    PUSH --> ORAS
    SEARCH --> HUB
    EXEC --> UI
    EXEC --> EXP
```

The CLI dispatches subcommands. `run` is the core path: load + validate the Locusfile, plan the DAG (resolving and type-checking every stage edge), then execute stages in dependency order through the selected runtime backend, materializing typed `Locus_Artifact`s in the run workspace and threading provenance through a run-scoped lineage store. `pull`/`push`/`search` talk OCI to Harbor. `build` packages an image from its manifest and certifies provenance conformance.

## Data Models

All models are Pydantic v2. The `Locus_Artifact`, `Artifact_Type`, and provenance structures align with the engine's `ProvenancedTable`/`IntermediateRepresentation` so the contract is shared, not re-invented.

```python
from __future__ import annotations
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field


class ArtifactKind(StrEnum):
    IR = "ir"
    TABLE = "table"
    CHUNKS = "chunks"
    EMBEDDINGS = "embeddings"
    GRAPH = "graph"


class ArtifactType(BaseModel):
    """A versioned artifact type, e.g. kind=table version=(1,0) -> 'table/v1'."""
    kind: ArtifactKind
    major: int = 1
    minor: int = 0

    def tag(self) -> str:
        return f"{self.kind.value}/v{self.major}"

    def compatible_with(self, consumer: "ArtifactType") -> "Compat":
        if self.kind != consumer.kind or self.major != consumer.major:
            return Compat.INCOMPATIBLE
        if self.minor != consumer.minor:
            return Compat.MINOR_DIFF
        return Compat.OK


class Compat(StrEnum):
    OK = "ok"
    MINOR_DIFF = "minor_diff"   # compatible with warning (Req 6.6)
    INCOMPATIBLE = "incompatible"


class LocusArtifact(BaseModel):
    """The only structure that crosses a stage boundary (Req 6.1)."""
    type: ArtifactType
    payload_path: str            # Arrow/Parquet file in the Run_Workspace (Req 6.2)
    lineage_path: str | None = None   # serialized lineage graph for this artifact
    produced_by: str             # stage id
    engine_mode: str = "deterministic"  # "deterministic" | "llm"


class PrivacyClass(StrEnum):
    LOCAL_ONLY = "local_only"
    CALLS_EXTERNAL = "calls_external"   # an LLM-backed image (Req 12.2)


class ImageManifest(BaseModel):
    """Build-time declaration of an image (Req 9.2)."""
    name: str
    version: str
    description: str = ""
    accepts: list[ArtifactType] = Field(default_factory=list)
    emits: ArtifactType
    engine_modes: list[str] = Field(default_factory=lambda: ["deterministic"])
    privacy_class: PrivacyClass = PrivacyClass.LOCAL_ONLY
    provenance_conformant: bool = False   # set by build-time certification (Req 9.4)
    entrypoint: str                       # import path of the capability callable
    dependencies: dict[str, str] = Field(default_factory=dict)  # pinned (Req 9.3)


class StageSpec(BaseModel):
    """One stage in a Locusfile pipeline."""
    id: str
    image: str                       # "name:version"
    needs: list[str] = Field(default_factory=list)   # dependency ids (Req 5.4)
    source: "SourceSpec | None" = None               # override pipeline source
    config: dict[str, Any] = Field(default_factory=dict)


class SourceSpec(BaseModel):
    type: str                        # "files" | "url" | "api" | "sql"
    path: str | None = None
    uri: str | None = None


class PortSpec(BaseModel):
    ui: int | None = None
    api: int | None = None


class Locusfile(BaseModel):
    """The run-configuration surface (Req 3)."""
    image: str | None = None          # single-image shorthand
    source: SourceSpec | None = None
    pipeline: list[StageSpec] = Field(default_factory=list)
    volumes: list[str] = Field(default_factory=list)
    ports: PortSpec = Field(default_factory=PortSpec)
    schema_mode: str = "infer"
    schema_ref: str | None = None
    llm: dict[str, Any] | None = None
    env_file: str | None = None
    export: dict[str, Any] | None = None
    review: dict[str, Any] | None = None
    mode: str = "strict"              # "strict" | "permissive" (Req 7.7/7.8)
```

## Components and Interfaces

### CLI commands (Typer)

```python
# locus <command>
def pull(image: str) -> None: ...                       # Req 2
def run(locusfile: str = "locusfile.yaml",
        runtime: str = "process") -> None: ...          # Req 1, 5, 8
def build(manifest: str = "locus.image.yaml") -> None: ...  # Req 9
def push(image: str, private: bool = False) -> None: ...    # Req 10
def search(query: str = "") -> None: ...                # Req 11
def login(registry: str | None = None) -> None: ...     # Req 10.1
def init(path: str = ".") -> None: ...                  # Req 4.4 (.env + gitignore)
def config_set_key(provider: str, key: str) -> None: ... # keyring (Req 4.1)
```

### LocusfileLoader

Loads YAML, validates against the `Locusfile` model, performs credential safety checks (reject raw keys, enforce `.env` gitignore/untracked — Req 4.3/4.5), and resolves a single-image shorthand into a one-stage pipeline. Raises `ConfigError` with the offending setting (Req 3.7).

### PipelinePlanner

```python
class PipelinePlanner:
    def plan(self, lf: Locusfile, manifests: dict[str, ImageManifest]) -> PipelinePlan:
        """Build the DAG, detect cycles (Req 5.6), topologically order stages, and
        STATIC-CHECK every edge's artifact-type compatibility BEFORE execution
        (Req 6.4/6.5). A major-version mismatch fails; a minor mismatch warns
        (Req 6.6). Also verifies provenance-conformance per mode (Req 7.7/7.8)."""
```

`PipelinePlan` holds the ordered stages, parallelizable groups (waves of independent stages, Req 5.5), and the validated edge map. Planning fails fast: no stage runs if any edge is incompatible or a cycle exists.

### StageExecutor and Runtime backends

```python
class RuntimeBackend(Protocol):
    name: str
    def run_stage(self, image: ResolvedImage, inputs: list[LocusArtifact],
                  ctx: StageContext) -> LocusArtifact: ...

class ProcessBackend:   # default (Req 1.3) — per-image venv, in-process engine call
    ...
class DockerBackend:    # optional (Req 1.4); errors clearly if Docker absent (Req 1.5)
    ...
```

`StageExecutor` walks the plan wave by wave: gathers each stage's input artifacts (the pipeline source for root stages, dependency outputs otherwise — Req 5.3/5.4), invokes the backend, writes the output `Locus_Artifact` (Arrow file) to the run workspace, and records lineage. Stage caching (Req 5.8): if a stage's input artifact hashes and image version match a prior run, reuse the cached output.

### CrossStageProvenance

Wraps the engine's `ProvenanceComposer`/`LineageStore`. As artifacts flow between stages, cell ids and lineage edges are preserved in a run-scoped `Lineage_Store`; the terminal artifact's cells resolve to original `Source_Location`s (Req 7.5/7.6). Conformance is checked at build time (Req 9.4) and enforced at plan time per mode (Req 7.7/7.8).

### Distribution: OCI client + cache

```python
class ImageStore:
    def pull(self, ref: str) -> ResolvedImage: ...   # ORAS pull -> cache (Req 2.1)
    def cached(self, ref: str) -> ResolvedImage | None: ...   # (Req 2.2)
    def push(self, image: BuiltImage, *, private: bool) -> None: ...  # (Req 10)
    def search(self, query: str) -> list[ImageSummary]: ...   # (Req 11)
```

Images are OCI artifacts: the manifest + a layer with the capability code + pinned deps. Private/public visibility maps to Harbor project visibility (Req 10.3/10.4); pulls authenticate via the `Registry_Credential`, which is wholly separate from LLM keys (Req 10.8).

### ImageBuilder

Packages an `ImageManifest` + entrypoint into a `BuiltImage`, pins dependency versions (Req 9.3), and runs the engine's `conformance` harness (`probe_extraction_engine`) against the capability to set `provenance_conformant` (Req 9.4/9.5).

### Result serving and export

`ResultServer` (FastAPI) serves the final artifact on the mapped UI port (Req 8.1): rows, per-cell faithfulness + source location, flagged rows, and the engine mode (Req 8.2/8.3), reading directly from the engine's emitted DataFrame + `_lineage` column. `Exporter` writes the configured format (Req 8.4). Both are local; no hosted service (Req 8.5).

## Error Handling

| Class | Examples | Behavior |
|-------|----------|----------|
| Plan-fatal, fail-fast | cycle in DAG, artifact-type mismatch, non-conformant stage in strict mode, missing image | raise before any stage runs (Req 5.6, 6.5, 7.7, 2.4) |
| Config | invalid Locusfile, raw key in file, git-tracked `.env` | reject with offending setting (Req 3.7, 4.3, 4.5) |
| Backend | Docker selected but absent | error identifying the backend; no silent fallback (Req 1.5) |
| Permissive degradation | non-conformant stage in permissive mode | continue; mark downstream cells lineage-broken (Req 7.8) |
| Runtime privacy | external-LLM stage about to send data | consent notice before egress (Req 12.1) |

Errors derive from a `LocusRuntimeError` hierarchy, distinct from but mirroring the engine's `LocusError`.

## Correctness Properties

### Property 1: Fail-fast type safety

For any composed pipeline, no stage executes unless every dependency edge is artifact-type compatible (major version equal, kind equal). An incompatible edge raises before execution.

**Validates: Requirements 6.4, 6.5**

### Property 2: Acyclic execution

A pipeline graph containing a cycle never executes any stage and reports the cycle.

**Validates: Requirements 5.6**

### Property 3: Dependency ordering

A stage executes only after all stages in its `needs` have completed, and its inputs are exactly those dependencies' outputs (or the pipeline source for root stages).

**Validates: Requirements 5.3, 5.4**

### Property 4: End-to-end provenance survival

Every cell in the terminal artifact resolves, through the run lineage store, to at least one originating `Source_Location`, across all intermediate stages.

**Validates: Requirements 7.1, 7.5, 7.6**

### Property 5: Conformance gating

In strict mode a non-conformant stage fails the run; in permissive mode it continues and the affected downstream cells are marked lineage-broken.

**Validates: Requirements 7.7, 7.8**

### Property 6: Credential locality

No LLM credential or user data is transmitted to any hosted Locus service; credentials resolve only from local sources and a raw key in the Locusfile is rejected.

**Validates: Requirements 4.1, 4.2, 4.3**

### Property 7: Registry/credential separation

The registry credential authorizes only image pull/push and never grants access to LLM provider credentials.

**Validates: Requirements 10.8**

### Property 8: Privacy disclosure honesty

A run containing an external-LLM image never presents a blanket data-stays-local claim and surfaces a consent notice before data leaves.

**Validates: Requirements 12.1, 12.3**

## Testing strategy

1. **Locusfile validation** — minimal (source + image) accepted; raw-key rejection; `.env` gitignore/untracked guardrails; single-image shorthand expands to one stage.
2. **Planner unit tests** — DAG construction, cycle detection, topological waves, edge type-check (compatible / minor-warn / major-fail), conformance gating per mode.
3. **Interchange round-trip** — a `Locus_Artifact` written by one stage (Arrow) reads back identically in the next; lineage path resolves.
4. **Cross-stage provenance** — a two-stage pipeline (extract → redact) where the final masked cell still resolves to the original source; reuses the engine's conformance assertions.
5. **Backend tests** — process backend runs a stub image end-to-end; docker backend errors cleanly when Docker is absent (mocked).
6. **Distribution** — pull/cache hit-miss against a mocked OCI client; private-image auth; version resolution default.
7. **Serving/export** — FastAPI test client returns rows + provenance + engine mode; exporter writes the configured format.
8. **Privacy** — consent fires before an external-LLM stage; no blanket local claim when such a stage is present.
9. **Golden two-stage pipeline** — using two real engine-backed stub images, assert the typed DAG, provenance survival, and final emitted output end-to-end.

## Key design decisions and rationale

- **Separate `locus` package depending on `locus_engine`.** Keeps the engine reusable and the runtime's heavier deps (Typer, FastAPI, oras, optional docker) out of the engine.
- **Artifacts pass by file path in a run workspace, not in memory.** Enables the Docker backend (cross-process), stage caching (content-addressed), and large datasets — and reuses the engine's Arrow/Parquet emitters.
- **Static type-check before any execution.** Composition is only trustworthy if mismatches fail fast; this is a pipeline-level type system over the fixed `ArtifactType` set.
- **Provenance enforced at build (certification) and plan (gating).** Reuses the Layer 1 conformance harness so the guarantee is identical end to end; non-conformant images are visible, never silent.
- **OCI/Harbor borrowed, CLI registry-agnostic.** No registry is built; the default hub is swappable to GHCR/ECR/self-hosted Harbor via config.
```
