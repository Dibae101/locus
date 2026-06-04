# Locus — Status

_Snapshot for review. Everything below is verified, not assumed._

## Shipped and live

- **Published to PyPI:** `pip install locus-etl` works (verified from a clean venv →
  `locus run` produced a grounded table). Latest version `0.0.2`, CLI command `locus`.
- **GitHub:** all work on `main` at `github.com/Dibae101/locus`; tags `v0.0.1`, `v0.0.2` pushed.
- **Tests:** 236 passing, ruff + mypy strict clean, on Python 3.11/3.12 (CI workflow committed).
- **Every CLI command smoke-tested** end-to-end (`scripts/smoke_test.sh`): version,
  catalog list/seed, validate, run (single + multi-stage), search, inspect, pull.

### 0.0.2 (latest)
- Added missing `packaging` core dependency (fixed `ModuleNotFoundError` on `pull`/`search`).
- Corrected optional-extra install hints to the real distribution name:
  `pip install 'locus-etl[pdf|llm|oci|serve]'`.
- `locus version` now derives from installed package metadata (no more stale `0.0.1`).

## What works

| Capability | Status |
|---|---|
| Engine (ingest→parse→extract→clean→ground→emit, cell provenance) | ✅ |
| CLI: run / validate / build / push / pull / search / inspect / catalog / hub / login | ✅ |
| 16-image catalog (extractors, converters, cleaners, pii-redactor, anomaly-flagger, …) | ✅ |
| Multi-stage pipelines (typed DAG, static type-check, cross-stage provenance) | ✅ |
| Result preview UI (`locus run --serve`) | ✅ |
| Locus Hub web UI (`locus hub`) — browse/search + trust metadata | ✅ |
| Local registry (default) + OCI/Harbor backend (`LOCUS_REGISTRY`) | ✅ (OCI unit-tested w/ fake client) |
| Harbor deploy stack (`deploy/harbor/`) | ✅ compose + guide |

## Known limits (need external infra to validate — not bugs)

- **OCI/Harbor backend** unit-tested against a fake oras client; not yet run against a
  live registry. Use `deploy/harbor/docker-compose.yml` to stand one up and validate.
- **Docker run backend** (`--runtime=docker`) errors cleanly when no daemon; real
  container execution needs a Docker daemon to implement/test.
- **Docling/OCR parsers** not wired (CSV / PDF-text / HTML / records parsers work).

## To take it further (optional)

1. Validate the live registry path: `docker compose -f deploy/harbor/docker-compose.yml up -d`
   then `LOCUS_REGISTRY=localhost:5000 LOCUS_INSECURE=1 locus catalog seed` and browse :8800.
2. Wire Docling for higher-fidelity PDF tables.
3. Expand the catalog toward the full 65 planned images.
4. Cut `0.1.0`: bump `pyproject.toml` version, `uv build`, `uv publish`, tag.

## Publishing future versions

`.env` holds `UV_PUBLISH_TOKEN`. Then:
```bash
set -a; source .env; set +a
uv build && uv publish
```
(See `PUBLISHING.md`. Never type the token into a prompt; the env var avoids prompts.)
