"""Command-line entry point (`uv run wiqaya --help`)."""

from __future__ import annotations

import json

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


@app.command("content-check")
def content_check() -> None:
    """Validate config, reference content, rules (incl. source verification) and the message library."""
    from wiqaya.common.content_check import run

    problems, summary = run()
    typer.echo(json.dumps(summary, indent=2, ensure_ascii=False))
    if problems:
        typer.echo(f"\n{len(problems)} problem(s):")
        for p in problems:
            typer.echo(f"  - {p}")
        raise typer.Exit(1)
    typer.echo("content-check: OK")


@app.command("docs-codes")
def docs_codes() -> None:
    """Regenerate docs/CODES.md from content/reference/codes.yaml."""
    from wiqaya.common.codes_doc import write

    write()
    typer.echo("wrote docs/CODES.md")


if __name__ == "__main__":
    app()
