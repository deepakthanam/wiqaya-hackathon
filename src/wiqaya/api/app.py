"""FastAPI application (`/api/v1`). Population prioritisation, not a clinical decision. Simulated cohort."""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from wiqaya import __version__
from wiqaya.api.analyst_routes import router as analyst_router
from wiqaya.api.routers import router

app = FastAPI(
    title="Wiqaya API",
    version=__version__,
    description="Population prioritisation, not a clinical decision. All data is a simulated cohort.",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
)

origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["GET", "POST"],
                   allow_headers=["*"])  # fmt: skip


@app.middleware("http")
async def security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Data-Label"] = "Simulated cohort"
    return response


app.include_router(router)
app.include_router(analyst_router)
