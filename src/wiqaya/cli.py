"""Command-line entry point. Subcommands are added milestone by milestone."""

import typer

from wiqaya import __version__

app = typer.Typer(help="Wiqaya command-line tools (synthetic data only).", no_args_is_help=True)


@app.command()
def version() -> None:
    """Print the Wiqaya version."""
    typer.echo(__version__)


@app.command()
def todo(target: str) -> None:
    """Placeholder for Makefile targets not built yet."""
    typer.echo(f"[wiqaya] '{target}' is not implemented yet; see PLAN.md for its milestone.")


if __name__ == "__main__":
    app()
