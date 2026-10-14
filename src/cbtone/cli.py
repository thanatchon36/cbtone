"""cbtone command-line interface."""

from __future__ import annotations

import typer

from cbtone import __version__

app = typer.Typer(help="Hawkish/dovish tone signals from public central-bank communication.")


@app.command()
def version() -> None:
    """Print the cbtone version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
