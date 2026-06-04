# Locus

Turn any unstructured corpus into validated, **source-grounded** tabular data — ready to feed an LLM.

Locus packages data operations as reusable, versioned **images**. You pull an image, point it at your own data, run it locally, and get a clean table where **every cell carries its source location and a faithfulness score**. Images compose into pipelines, and you can publish your own to Locus Hub (public or private).

## Architecture (layered)

![Locus layered architecture](docs/architecture.png)

The diagram is generated from [`docs/generate_architecture_diagram.py`](docs/generate_architecture_diagram.py) (PNG + SVG in `docs/`).

### Layer summary

| Layer | Spec | Responsibility |
|-------|------|----------------|
| **Layer 1 — Engine** | `unstructured-to-tabular-etl` | Raw corpus -> validated, source-grounded table. Connectors, parsing, extraction, cleaning, the cell-level grounding/faithfulness contract, review. Embedded inside every image. |
| **Layer 2 — Runtime** | `locus-image-runtime` | Packaging, CLI, Locusfile, image pull, multi-image composition (DAG), typed stage interchange, cross-stage provenance, serve/export, and publishing to Locus Hub. |

## Key properties

- **Local-first.** Default runtime is a plain Python process — no daemon, no Linux VM. Docker is an optional backend.
- **Privacy is explicit.** Deterministic engine keeps data local; the LLM engine activates only when you add a key, with a consent notice before any data leaves.
- **Trust travels with the data.** Provenance and faithfulness survive every pipeline stage, from extraction through merge and redaction.

## Documentation

Detailed design lives in the spec documents:

- Layer 1 engine — [`.kiro/specs/unstructured-to-tabular-etl/requirements.md`](.kiro/specs/unstructured-to-tabular-etl/requirements.md)
- Layer 2 runtime — [`.kiro/specs/locus-image-runtime/requirements.md`](.kiro/specs/locus-image-runtime/requirements.md)
- Image catalog (planned images + build order) — [`.kiro/specs/locus-image-runtime/image-catalog.md`](.kiro/specs/locus-image-runtime/image-catalog.md)
- Architecture & decision log — [`.kiro/specs/unstructured-to-tabular-etl/architecture-notes.md`](.kiro/specs/unstructured-to-tabular-etl/architecture-notes.md)

## Status

**Layer 1 engine: feature-complete.** **Layer 2 runtime: feature-complete (all 12 build stages done).** Raw corpus → validated, source-grounded table with cell-level provenance; a deterministic default engine and opt-in guardrailed LLM engine; cleaning/dedup; human-in-the-loop review; file/HTTP/REST/SQL connectors with CSV/PDF/HTML/records parsers and DataFrame/Parquet/SQL emitters. The `locus` CLI runs single images and multi-stage pipelines (typed DAG with static type-check + cross-stage provenance), builds/publishes/pulls images via a local registry, and serves a local result UI with the provenance viewer. 208 tests, CI on Python 3.11/3.12 (ruff + mypy strict + pytest).

```bash
pip install locus            # CLI + engine (extras: [pdf] [llm] [serve] [dedup] ...)
locus init                   # gitignore .env
locus run locusfile.yaml     # run a pipeline, get a grounded table
locus run locusfile.yaml --serve --port 8080   # preview UI with provenance
locus build / push / pull / search / inspect   # image lifecycle
```

Remaining work is the OCI/Harbor registry backend (the local registry is the functional default today) and the official image catalog.

```python
from locus_engine import (
    Pipeline, PipelineConfig, PluginRegistry,
    FileConnector, CsvParser, Connector, Parser, SourceRef,
)

registry = PluginRegistry()
registry.register(FileConnector(), Connector)
registry.register(CsvParser(), Parser)

config = PipelineConfig.load({"source": {"type": "files", "path": "./data"}})
pipeline = Pipeline(config, registry)

out = pipeline.run([SourceRef(uri="./data/invoices.csv", kind="file")])
frame = pipeline.emit(out)          # pandas DataFrame with a _lineage column
print(frame)
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © 2026 Dibae101
