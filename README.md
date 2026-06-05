# Locus

Turn any unstructured corpus into validated, **source-grounded** tabular data — ready to feed an LLM.

[![PyPI](https://img.shields.io/pypi/v/locus-etl.svg)](https://pypi.org/project/locus-etl/)
[![Python](https://img.shields.io/pypi/pyversions/locus-etl.svg)](https://pypi.org/project/locus-etl/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Locus packages data operations as reusable, versioned **images**. You pull an image, point it at your own data, run it locally, and get a clean table where **every cell carries its source location and a faithfulness score**. Images compose into pipelines, and you can publish your own to Locus Hub (public or private).

## Install

```bash
pip install locus-etl                  # core: CLI + engine + CSV/records/provenance
pip install "locus-etl[standard]"      # + PDF, HTML, SQL, normalize, result UI
pip install "locus-etl[all]"           # everything, incl. OCR/LLM/embeddings (heavy)
```

The CLI command is `locus` (Python 3.11+). Quote the brackets — your shell treats them
as a glob otherwise (`zsh: no matches found`).

Pick targeted extras if you prefer a lean install:
`pip install "locus-etl[pdf,serve,llm,oci]"` — `pdf` (PDF parsing), `html`, `sql`,
`normalize`, `serve` (Hub/result UI), `llm` (LLM engine), `ocr`, `dedup`, `embeddings`,
`docling`, `oci` (OCI registry), `docker`.

## Quickstart

```bash
locus catalog list                  # see the official image catalog
printf 'name,amount\nAcme,100\nGlobex,200\n' > data.csv
cat > locusfile.yaml <<EOF
image: doc-to-tables
source: { type: files, path: ./data.csv }
EOF
locus run locusfile.yaml --export out.csv   # grounded table + _lineage column
locus run locusfile.yaml --serve            # interactive result view (table + charts)
locus hub                                    # browse the catalog in a local web UI
```

Declare output and a live visualization right in the Locusfile (Dockerfile-style):

```yaml
image: doc-to-tables
source: { type: files, path: ./data.csv }
export:
  path: ./out.json        # csv | parquet | json | markdown (inferred from extension)
expose: 8080              # serve table + column charts at http://127.0.0.1:8080
```

## Supported inputs

Out of the box (no extra dependencies): CSV/TSV, JSON, Markdown (pipe tables), HTML,
plain text and common source files, DOCX, PPTX, XLSX, ODT, EPUB, and ZIP archives
(members parsed and merged). PDF text is available with the `pdf` extra; images need
OCR (roadmap). Documents with tables yield those tables; documents that are prose yield
a grounded `element | text | location` table so any readable file still produces a
presentable result.

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
pip install locus-etl        # CLI command is `locus`; extras: [pdf] [llm] [serve] [oci] ...
locus init                   # gitignore .env
locus catalog list           # see the official image catalog
locus run locusfile.yaml     # run a pipeline, get a grounded table
locus run locusfile.yaml --serve --port 8080   # preview UI with provenance
locus hub                    # browse the image catalog in a local web UI
locus build / push / pull / search / inspect   # image lifecycle
```

Remaining work is the official image catalog and a hub-side discovery index. The
**OCI/Harbor registry backend is implemented** (`OrasImageStore`): set `LOCUS_REGISTRY`
(and optionally `LOCUS_NAMESPACE`) to push/pull/inspect against Harbor, GHCR, ECR, or any
OCI registry; otherwise a local filesystem registry is the zero-config default.

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
