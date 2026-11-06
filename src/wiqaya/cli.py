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


@app.command()
def data(seed: int = 42, n: int = 20000) -> None:
    """Generate the synthetic cohort, NDJSON, hidden truth, Parquet/DuckDB, gaps and the population report."""
    import time

    from wiqaya.generator.report import write_report
    from wiqaya.generator.run import run
    from wiqaya.rules.run import persist_gaps, run_gaps

    t = time.perf_counter()
    meta = run(seed, n)
    gaps, stats = run_gaps()
    persist_gaps(gaps, stats)
    path = write_report(meta, gaps, stats)
    typer.echo(
        json.dumps(
            {**meta, "gaps": stats["gaps"], "report": str(path), "seconds": round(time.perf_counter() - t, 1)}, indent=1
        )
    )


@app.command()
def gaps() -> None:
    """Run the care-gap engine + family graph and persist care_gaps."""
    from wiqaya.rules.run import persist_gaps, run_gaps

    df, stats = run_gaps()
    persist_gaps(df, stats)
    typer.echo(json.dumps(stats, indent=1, default=str))


@app.command()
def load(
    mode: str = typer.Option(None, help="sample | full (default: FHIR_LOAD env or sample)"),
    wait: bool = typer.Option(False, help="wait up to 5 minutes for HAPI to answer first"),
) -> None:
    """Load NDJSON into HAPI FHIR via transaction bundles."""
    import time

    from wiqaya.fhir.loader import get
    from wiqaya.fhir.loader import load as do_load

    if wait:
        for _ in range(150):
            try:
                get("metadata")
                break
            except Exception:
                time.sleep(2)

    out = do_load(mode)
    typer.echo(json.dumps(out, indent=1))
    if out["error_count"]:
        raise typer.Exit(1)


@app.command()
def train() -> None:
    """Train + calibrate models, score, rank, fairness floor and capacity fit."""
    from wiqaya.models.pipeline import run

    m = run()
    keys = (
        "flags",
        "capacity_total",
        "flags_per_slot",
        "assigned",
        "van_assigned",
        "household_bundled",
        "capacity_violations",
        "seconds",
    )
    out = {k: m[k] for k in keys}
    out["model_r_auroc"] = m["model_r"]["test_calibrated"].get("auroc")
    out["model_n_auroc"] = m["model_n"]["test_calibrated"].get("auroc")
    out["fit"] = {k: v for k, v in m["fit"].items() if k != "detail"}
    out["fairness_adjustments"] = m["fairness"]["adjustments"]
    typer.echo(json.dumps(out, indent=1, default=str))


@app.command()
def simulate(sensitivity: bool = typer.Option(True, help="also run the sensitivity scenarios")) -> None:
    """Simulate 12 weeks under baseline and Wiqaya policies (common random numbers)."""
    from wiqaya.simulate.run import run, summary

    res = run(sensitivity=sensitivity)
    typer.echo(summary(res).to_string())
    typer.echo(
        json.dumps(
            {
                "primary_endpoint": res["primary_endpoint"],
                "sensitivity": res.get("sensitivity"),
                "seconds": res["seconds"],
            },
            indent=1,
            default=str,
        )
    )


@app.command()
def evaluate() -> None:
    """Write docs/EVALUATION.md from the latest runs."""
    from wiqaya.evaluate.report import write

    write()
    typer.echo("wrote docs/EVALUATION.md")


if __name__ == "__main__":
    app()
