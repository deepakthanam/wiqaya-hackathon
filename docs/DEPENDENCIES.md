# Dependencies

## Runtime services
| Service | Image / version | Role | Ports |
|---|---|---|---|
| HAPI FHIR JPA server | `hapiproject/hapi:v8.12.0-2` (FHIR R4) | System of record | 8080 (localhost only; internal-only in deployment) |
| PostgreSQL | `postgres:16-alpine` | HAPI database | internal |
| Wiqaya API | Python 3.11 + FastAPI/Uvicorn (`docker/api.Dockerfile`) | `/api/v1` | 8000 |
| Wiqaya web | Node 20 + Next.js 14 (`web/Dockerfile`) | Consoles | 3000 |
| Caddy (deployment) | `caddy:2.8` | Reverse proxy, automatic HTTPS | 80/443 |

## Tooling
| Tool | Version used | Notes |
|---|---|---|
| Python | 3.11 (pinned in `.python-version`) | via `uv` |
| uv | 0.13.x | `uv sync` installs from `uv.lock` |
| Node.js | 20+ (tested on 24) | |
| pnpm | 9.15 via `corepack pnpm` | lockfile `web/pnpm-lock.yaml` |
| Docker + Compose | Compose v2+ | `make up` |
| GNU make + POSIX shell | | On Windows use Git Bash |
| Java 17 | Only for the optional Synthea path | Not used |

## Python libraries (main)
pydantic 2, PyYAML, numpy, pandas, pyarrow, duckdb, networkx, scikit-learn, lightgbm, shap, ortools (CP-SAT), fastapi,
uvicorn, httpx, itsdangerous, typer, rich. Dev: pytest, hypothesis, ruff, mypy. Exact versions are in `uv.lock`. Licences
are in `THIRD_PARTY_LICENSES.md`.

## Web libraries (main)
next 14.2, react 18.3, recharts 2.12, leaflet 1.9 + react-leaflet 4.2, react-markdown 9 + remark-gfm, openapi-fetch,
openapi-typescript (dev), Playwright (dev), Tailwind CSS 3.4.

## External network calls
- **At build time only, optional:**
  - Overpass and Nominatim (OSM), NCBI E-utilities (ClinVar), guideline URLs (source verification).
  - The results are committed, so a clean clone works offline: `make content-check` defaults to offline, and `make fetch-reference` refreshes them.
- **At run time:**
  - OSM map tiles in the browser. The planner falls back to an SVG grid if tiles are blocked.
  - No LLM calls by default.

## Hardware
`make demo` on a 16 GB laptop:
- about 2 GB for HAPI and Postgres;
- about 2 GB for the pipeline at peak;
- about 1 GB for the web dev server.
