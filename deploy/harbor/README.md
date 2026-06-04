# Locus Hub deployment

Run a hosted Locus Hub: an OCI registry that stores the image catalog plus the Locus
Hub web UI for browsing it. The Locus CLI and Hub UI speak plain OCI, so the registry
is swappable (a local `registry:2` for dev, full Harbor for production, or GHCR/ECR).

## Quick start (local dev hub)

```bash
# 1. start the registry + Hub UI
docker compose -f deploy/harbor/docker-compose.yml up -d

# 2. publish the official catalog into it (from a machine with the CLI)
pip install "locus-etl[oci]"
export LOCUS_REGISTRY=localhost:5000
export LOCUS_INSECURE=1
locus catalog seed

# 3. browse the catalog
open http://localhost:8800

# 4. users pull from it
LOCUS_REGISTRY=localhost:5000 LOCUS_INSECURE=1 locus pull doc-to-tables:0.1.0
```

## Production: real Harbor

For RBAC, vulnerability scanning, replication, signing, and Harbor's own admin UI,
deploy Harbor with its official installer (https://goharbor.io/docs/), then point Locus
at it:

```bash
export LOCUS_REGISTRY=hub.your-domain.com
export LOCUS_NAMESPACE=library
locus login -u <user> -p <token>     # obtains a registry credential
locus catalog seed                    # publish the catalog
locus hub --port 8800                 # or run the Hub UI as a service
```

The Hub UI reads images and their Locus trust metadata (accepted/emitted artifact
types, engine modes, privacy class, provenance conformance) directly from the
registry, so it works against any OCI backend.

## Environment variables

| Variable          | Purpose                                              |
|-------------------|------------------------------------------------------|
| `LOCUS_REGISTRY`  | registry host; unset = local filesystem registry     |
| `LOCUS_NAMESPACE` | namespace/project for images (default `library`)     |
| `LOCUS_INSECURE`  | `1` to allow plain HTTP (local dev only)             |
| `LOCUS_HOME`      | local state dir (default `~/.locus`)                 |

## Notes

- The compose file uses CNCF `registry:2` for a minimal working hub. It has no auth or
  UI of its own — the Locus Hub UI provides browse/search. Use full Harbor for anything
  multi-user or internet-facing.
- The Hub UI container installs `locus-etl` from PyPI at startup; pin a version
  (`locus-etl==0.0.1`) for reproducible deployments.
