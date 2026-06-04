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
    from locus.store import LocalImageStore

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


def _default_store() -> LocalImageStore:
    from pathlib import Path

    from locus.store import LocalImageStore

    root = Path.home() / ".locus" / "registry"
    return LocalImageStore(root=root)


@app.command()
def pull(image: str = typer.Argument(..., help="Image reference name:version.")) -> None:
    """Pull an image into the local cache."""
    store = _default_store()
    path = store.pull(image)
    typer.echo(f"Pulled {image} -> {path}")


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
    export: str = typer.Option("", "--export", help="Optional path to export the result."),
) -> None:
    """Run a Locusfile (single image or multi-stage pipeline) and produce a table."""
    from locus.loader import load_locusfile
    from locus.runner import run_pipeline

    lf = load_locusfile(locusfile)
    out = run_pipeline(lf)
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
    if export:
        if export.endswith(".parquet"):
            out.frame.to_parquet(export, index=False)
        else:
            out.frame.to_csv(export, index=False)
        typer.echo(f"Exported to {export}.")


if __name__ == "__main__":  # pragma: no cover
    app()
