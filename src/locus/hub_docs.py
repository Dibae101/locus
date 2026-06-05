"""User documentation content for the Locus Hub.

Each entry is a docs page rendered by the Hub (Docker-docs style). Content is written
in a tiny subset of Markdown (headings, code fences, lists, paragraphs) and rendered
to HTML by ``locus.hub``'s minimal renderer. Keeping docs here means the hosted Hub
ships its own user guide with no external site.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DocPage:
    slug: str
    title: str
    body: str  # tiny-markdown


PAGES: list[DocPage] = [
    DocPage(
        "getting-started",
        "Getting Started",
        """
# Getting Started

Locus turns unstructured data into validated, **source-grounded** tables. You pull an
image (a packaged data operation), point it at your data, and run it — every output
cell keeps a link back to where it came from and a faithfulness score.

## Install

```
pip install locus-etl                  # core: CLI + engine + CSV/records
pip install "locus-etl[standard]"      # + PDF, HTML, SQL, normalize, result UI
pip install "locus-etl[all]"           # everything, incl. OCR/LLM/embeddings (heavy)
```

The CLI command is `locus`. Requires Python 3.11+.

The core stays lightweight on purpose. Heavier, scenario-specific capabilities
(PDF, OCR, LLM, embeddings, dedup) are opt-in *extras* so a CSV user doesn't download a
machine-learning toolchain. Quote the brackets so your shell doesn't treat them as a
glob (`zsh: no matches found`). Targeted extras: `pdf`, `html`, `sql`, `normalize`,
`serve`, `llm`, `ocr`, `dedup`, `embeddings`, `docling`, `oci`, `docker` — e.g.
`pip install "locus-etl[pdf,serve]"`.

## Your first run

1. Make a CSV at `./data/input.csv`.
2. Create `locusfile.yaml`:

```
image: doc-to-tables
source:
  type: files
  path: ./data/input.csv
```

3. Run it:

```
locus run locusfile.yaml --export out.csv
```

You'll get a table plus a `_lineage` column carrying provenance for every cell.

## See the catalog

```
locus catalog list          # all official images
locus pull invoice-extractor
locus search                # what's in your local registry
locus inspect invoice-extractor
```

## Preview in the browser

```
locus run locusfile.yaml --serve --port 8080
```
""",
    ),
    DocPage(
        "concepts",
        "Concepts",
        """
# Concepts

## Image
A packaged, versioned data operation (e.g. `doc-to-tables`). It contains logic, not
data. You bring the data. Images compose into pipelines.

## Locusfile
A small YAML file that says which image(s) to run, where your data is, and how to
output it. Only `image` (or `pipeline`) and `source` are required.

## Provenance & faithfulness
Every cell carries its source location and a faithfulness score (0–1). Rows below the
grounding threshold are flagged. This is what makes Locus output trustworthy.

## Engines
- **Deterministic** (default): pure-Python, no LLM, data stays local.
- **LLM** (opt-in): activates only when you supply an API key; bounded to fuzzy
  field-mapping under guardrails.

## Pipelines (composition)
Chain images with `needs:` to build a DAG. Locus type-checks every stage boundary
before running and carries provenance across stages.

## Registry & Hub
Images live in a registry (local by default, or an OCI registry like Harbor). The Hub
is the web UI for browsing them.
""",
    ),
    DocPage(
        "cli",
        "CLI Reference",
        """
# CLI Reference

```
locus version                 Print the version.
locus init [path]             Initialize a project (gitignore .env).
locus catalog list            List official catalog images.
locus catalog seed            Publish the catalog into your registry.
locus pull <name>:<ver>       Pull an image into the local cache.
locus search [query]          List images in your local registry.
locus inspect <name>          Show an image's contract.
locus run <locusfile>         Run a pipeline -> grounded table.
locus validate <locusfile>    Validate a Locusfile without running.
locus build <manifest>        Build a publishable image.
locus push <dir> [--private]  Publish a built image.
locus hub [--host --port]     Serve this Hub web UI.
locus login -u U -p P         Log in to an OCI registry.
```

## `locus run` flags

```
--export PATH        Write the result (.csv / .parquet / .json / .md).
--format FMT         Force the export format: csv | parquet | json | markdown.
--serve              Serve an interactive result visualization locally.
--port N             Override the serve/expose port.
--runtime process|docker   Execution backend (default process).
```

Every command supports `--help` for its own options.
""",
    ),
    DocPage(
        "locusfile",
        "Locusfile Reference",
        """
# Locusfile Reference

A Locusfile is YAML. Minimal:

```
image: doc-to-tables
source:
  type: files
  path: ./data/input.csv
```

## Fields

```
image:        single image ref (name[:version]); OR use `pipeline:`
source:       where your data is
  type:       files | url | api | sql
  path:       path (for files)
  uri:        uri (for url/api/sql)
schema_mode:  infer (default) | hint | strict
schema_ref:   path to a Python schema (strict mode)
llm:          provider/model/grounding_threshold (optional)
env_file:     path to a .env with credentials (optional)
export:       declarative output (optional)
  path:           where to write the result
  format:         csv | parquet | json | markdown (else inferred from path)
  include_lineage: keep the per-cell _lineage column (default true)
expose:       auto-serve a web visualization, like Dockerfile EXPOSE (optional)
              shorthand `expose: 8080`, or:
  port:           port to serve on (default 8080)
  host:           bind address (default 127.0.0.1; 0.0.0.0 to share)
  open:           auto-open the browser (default false)
mode:         strict (default) | permissive   (provenance conformance)
```

## Export and visualize

Declare output once in the Locusfile instead of passing flags every run:

```
image: doc-to-tables
source: { type: files, path: ./data/input.csv }
export:
  path: ./out.json
  format: json
expose: 8080        # open http://127.0.0.1:8080 to see the table + charts
```

`expose` serves an interactive view — the table with per-cell provenance plus
column profiles and charts — so you can eyeball results without opening a
spreadsheet. Bind to `0.0.0.0` only on trusted networks; the view has no auth.

## Pipeline (multi-image)

```
source:
  type: files
  path: ./data/input.csv
pipeline:
  - id: extract
    image: doc-to-tables
  - id: redact
    image: pii-redactor
    needs: [extract]
  - id: clean
    image: drop-flagged
    needs: [redact]
```

- `needs:` defines dependencies (a DAG); independent stages run in parallel.
- Stage `config:` passes options to that image (e.g. `keys`, `rename`, `columns`).
- Locus type-checks stage boundaries before running and carries provenance through.
""",
    ),
    DocPage(
        "hosting",
        "Hosting a Hub",
        """
# Hosting a Hub

The Hub is a normal web app. Run it anywhere:

```
locus hub --host 0.0.0.0 --port 8800
```

## With a real registry

Point Locus at an OCI registry (Harbor, GHCR, ECR) so the Hub and `pull` share it:

```
export LOCUS_REGISTRY=hub.example.com
locus login -u <user> -p <token>
locus catalog seed
locus hub --host 0.0.0.0 --port 8800
```

See `deploy/harbor/` and `deploy/cloudflare/` in the repo for ready-to-run stacks
(registry + Hub UI + optional Cloudflare Tunnel).
""",
    ),
]

PAGES_BY_SLUG = {p.slug: p for p in PAGES}
