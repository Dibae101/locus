"""Locus CLI entrypoint (Typer).

Subcommands are wired up across the Layer 2 build stages. Stage 0 establishes the
app and ``--version``; later stages add ``pull``, ``run``, ``build``, ``push``,
``search``, ``login``, and ``init``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from locus import __version__

if TYPE_CHECKING:
    from locus.store import ImageStore

app = typer.Typer(
    name="locus",
    help="Locus — pull, run, build, and publish data-processing images.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"locus {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    _version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show the Locus CLI version and exit.",
    ),
) -> None:
    """Locus command-line interface."""


@app.command()
def version() -> None:
    """Print the Locus CLI version."""
    typer.echo(f"locus {__version__}")


@app.command()
def init(path: str = typer.Argument(".", help="Project directory to initialize.")) -> None:
    """Initialize a project: ensure .env is gitignored."""
    from locus.loader import ensure_env_gitignored

    ensure_env_gitignored(path)
    typer.echo(f"Initialized Locus project in {path} (.env is gitignored).")


def _default_store() -> ImageStore:
    """Resolve the image store from environment.

    LOCUS_REGISTRY set -> OCI/Harbor backend (OrasImageStore); otherwise the local
    filesystem store at ~/.locus/registry. The CLI depends only on the protocol, so
    the backend is a config switch (Req 10.7).
    """
    import os
    from pathlib import Path

    registry = os.environ.get("LOCUS_REGISTRY")
    if registry:
        from locus.oci_store import OrasImageStore

        namespace = os.environ.get("LOCUS_NAMESPACE", "library")
        insecure = os.environ.get("LOCUS_INSECURE", "").lower() in {"1", "true", "yes"}
        return OrasImageStore(registry, namespace=namespace, insecure=insecure)

    from locus.store import LocalImageStore

    home = Path(os.environ.get("LOCUS_HOME", str(Path.home() / ".locus")))
    return LocalImageStore(root=home / "registry")


@app.command()
def login(
    username: str = typer.Option(..., "--username", "-u", help="Registry username."),
    password: str = typer.Option(..., "--password", "-p", help="Registry password/token."),
) -> None:
    """Log in to the configured OCI registry (set LOCUS_REGISTRY)."""
    import os

    if not os.environ.get("LOCUS_REGISTRY"):
        typer.echo("Set LOCUS_REGISTRY to use a remote registry.", err=True)
        raise typer.Exit(code=1)
    from locus.oci_store import OrasImageStore

    store = OrasImageStore(
        os.environ["LOCUS_REGISTRY"],
        namespace=os.environ.get("LOCUS_NAMESPACE", "library"),
    )
    store.login(username, password)
    typer.echo(f"Logged in to {os.environ['LOCUS_REGISTRY']}.")


@app.command()
def pull(image: str = typer.Argument(..., help="Image reference name:version.")) -> None:
    """Pull an image into the local cache."""
    store = _default_store()
    try:
        path = store.pull(image)
    except Exception:
        # Fall back: if it's a known catalog image, seed it locally then pull.
        from locus.catalog import resolve_catalog

        if resolve_catalog(image) is None:
            raise
        _ensure_catalog_seeded(store)
        path = store.pull(image)
    typer.echo(f"Pulled {image} -> {path}")


def _ensure_catalog_seeded(store: ImageStore) -> None:
    from locus.seed import seed_catalog

    seed_catalog(store)


catalog_app = typer.Typer(help="Manage the Locus image catalog.")
app.add_typer(catalog_app, name="catalog")


@catalog_app.command("list")
def catalog_list() -> None:
    """List the official catalog images."""
    from locus.catalog import all_images

    for img in all_images():
        m = img.manifest
        typer.echo(f"{m.name:26} {m.emits.tag():10} {m.description}")


@catalog_app.command("seed")
def catalog_seed() -> None:
    """Build and publish every catalog image to the configured registry."""
    store = _default_store()
    from locus.seed import seed_catalog

    refs = seed_catalog(store)
    typer.echo(f"Seeded {len(refs)} catalog images:")
    for ref in refs:
        typer.echo(f"  {ref}")


@app.command()
def hub(
    port: int = typer.Option(8800, "--port", help="Port for the Hub web UI."),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address (0.0.0.0 to expose)."),
    seed: bool = typer.Option(True, "--seed/--no-seed", help="Seed catalog if registry empty."),
) -> None:
    """Serve the Locus Hub web UI (browse + search images)."""
    store = _default_store()
    if seed and not store.search():
        from locus.seed import seed_catalog

        seed_catalog(store)
    from locus.hub import serve_hub

    shown = "127.0.0.1" if host in ("127.0.0.1", "localhost") else host
    typer.echo(f"Locus Hub at http://{shown}:{port} (Ctrl+C to stop).")
    serve_hub(store, host=host, port=port)


@app.command()
def search(query: str = typer.Argument("", help="Filter images by name substring.")) -> None:
    """List available images in the local registry."""
    store = _default_store()
    results = store.search(query)
    if not results:
        typer.echo("No images found.")
        return
    for s in results:
        vis = "private" if s.private else "public"
        conf = "conformant" if s.provenance_conformant else "non-conformant"
        typer.echo(f"{s.name}:{s.version}  emits={s.emits}  [{vis}, {conf}]")


@app.command()
def build(
    manifest: str = typer.Argument("locus.image.yaml", help="Path to the image manifest."),
    output: str = typer.Option("", "--output", "-o", help="Output image directory."),
) -> None:
    """Build a publishable image from a manifest."""
    from locus.builder import build_image

    out = build_image(manifest, output_dir=output or None)
    from locus.packaging import read_manifest

    m = read_manifest(out)
    conf = "conformant" if m.provenance_conformant else "non-conformant"
    typer.echo(f"Built {m.ref} -> {out}  [{conf}]")


@app.command()
def push(
    image_dir: str = typer.Argument(..., help="Built image directory to publish."),
    private: bool = typer.Option(False, "--private", help="Publish with private visibility."),
) -> None:
    """Publish a built image to the local registry."""
    from pathlib import Path

    store = _default_store()
    ref = store.push(Path(image_dir), private=private)
    vis = "private" if private else "public"
    typer.echo(f"Pushed {ref} ({vis}).")


@app.command()
def validate(
    locusfile: str = typer.Argument("locusfile.yaml", help="Path to the Locusfile."),
) -> None:
    """Validate a Locusfile without running it."""
    from locus.loader import load_locusfile

    lf = load_locusfile(locusfile)
    stages = lf.normalized_pipeline()
    typer.echo(f"OK: {locusfile} valid ({len(stages)} stage(s)).")


@app.command()
def run(
    locusfile: str = typer.Argument("locusfile.yaml", help="Path to the Locusfile."),
    export: str = typer.Option(
        "", "--export", help="Export path (overrides the Locusfile export.path)."
    ),
    export_format: str = typer.Option(
        "", "--format", help="Export format: csv | parquet | json | markdown."
    ),
    serve: bool = typer.Option(
        False, "--serve", help="Serve an interactive result visualization locally."
    ),
    port: int = typer.Option(0, "--port", help="Override the serve/expose port."),
    runtime: str = typer.Option(
        "process", "--runtime", help="Execution backend: process | docker."
    ),
) -> None:
    """Run a Locusfile (single image or multi-stage pipeline) and produce a table."""
    from locus.export import resolve_format, write_export
    from locus.loader import load_locusfile
    from locus.runner import run_pipeline

    lf = load_locusfile(locusfile)
    out = run_pipeline(lf, runtime=runtime)
    for w in out.warnings:
        typer.echo(f"warning: {w}", err=True)
    typer.echo(f"Produced {len(out.frame)} row(s) via the {out.engine_mode} engine.")
    if out.provenance:
        grounded = sum(
            1
            for row in out.provenance
            for cell in row.cells.values()
            if cell.source_ids and not cell.lineage_broken
        )
        total = sum(len(row.cells) for row in out.provenance)
        typer.echo(f"Provenance: {grounded}/{total} cells trace to a source origin.")

    # Export resolution: the --export flag overrides the Locusfile export.path; the
    # --format flag overrides export.format. Either source can request a write.
    declared_path = lf.export.path if lf.export else None
    declared_format = lf.export.format if lf.export else None
    include_lineage = lf.export.include_lineage if lf.export else True
    export_path = export or declared_path
    if export_path:
        fmt = resolve_format(export_path, export_format or declared_format)
        write_export(out.frame, export_path, fmt, include_lineage=include_lineage)
        typer.echo(f"Exported to {export_path} ({fmt}).")

    # Visualization: the Locusfile `expose:` field auto-serves (Dockerfile-style);
    # `--serve` forces it on. The `--port` flag overrides the resolved port.
    if serve or lf.expose is not None:
        from locus.serve import serve_result

        host = lf.expose.host if lf.expose else "127.0.0.1"
        resolved_port = port or (lf.expose.port if lf.expose else 0) or lf.ports.ui or 8080
        open_browser = lf.expose.open if lf.expose else False
        shown = "127.0.0.1" if host in ("127.0.0.1", "localhost") else host
        if host not in ("127.0.0.1", "localhost"):
            typer.echo(
                f"warning: exposing the result on {host}:{resolved_port} with no "
                "authentication; anyone who can reach this address can view the data.",
                err=True,
            )
        typer.echo(
            f"Visualizing result at http://{shown}:{resolved_port} (Ctrl+C to stop)."
        )
        serve_result(out, host=host, port=resolved_port, open_browser=open_browser)


@app.command()
def inspect(image: str = typer.Argument(..., help="Image reference name[:version].")) -> None:
    """Show an image's contract: types, engine modes, privacy, conformance."""
    store = _default_store()
    name = image.split(":", 1)[0]
    versions = sorted({s.version for s in store.search() if s.name == name})
    m = store.inspect(image)
    typer.echo(f"{m.name}:{m.version}")
    typer.echo(f"  versions:    {', '.join(versions) or m.version}")
    typer.echo(f"  emits:       {m.emits.tag()}")
    typer.echo(f"  accepts:     {', '.join(a.tag() for a in m.accepts) or '(source)'}")
    typer.echo(f"  engine modes:{', '.join(m.engine_modes)}")
    typer.echo(f"  privacy:     {m.privacy_class.value}")
    typer.echo(f"  conformant:  {m.provenance_conformant}")


if __name__ == "__main__":  # pragma: no cover
    app()
