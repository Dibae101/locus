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


if __name__ == "__main__":  # pragma: no cover
    app()
