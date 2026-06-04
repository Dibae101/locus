"""Locus CLI entrypoint (Typer).

Subcommands are wired up across the Layer 2 build stages. Stage 0 establishes the
app and ``--version``; later stages add ``pull``, ``run``, ``build``, ``push``,
``search``, ``login``, and ``init``.
"""

from __future__ import annotations

import typer

from locus import __version__

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
    if export:
        if export.endswith(".parquet"):
            out.frame.to_parquet(export, index=False)
        else:
            out.frame.to_csv(export, index=False)
        typer.echo(f"Exported to {export}.")


if __name__ == "__main__":  # pragma: no cover
    app()
