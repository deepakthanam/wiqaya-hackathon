"""FastAPI application. Milestone 0 exposes only the health check; routers arrive in Milestone 6."""

from __future__ import annotations

from fastapi import FastAPI

from wiqaya import __version__

app = FastAPI(
    title="Wiqaya API",
    version=__version__,
    description="Population prioritisation, not a clinical decision. All data is a simulated cohort.",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
)


@app.get("/api/v1/healthz", tags=["meta"])
def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "version": __version__, "data": "simulated cohort"}
