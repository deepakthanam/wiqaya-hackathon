# Wiqaya — build plan

Source brief: `PROMPT.md`. This plan turns it into milestones, files and risks.
Status: **Milestone 0 complete, waiting for approval.** Today is 2026-11-07; submission is 2026-11-20.

## Schedule

The brief targets M0–3 by 13 Nov. We start on 7 Nov, so the time is tight but workable.

| Day(s) | Milestone | Main output |
|---|---|---|
| 7 Nov | M0 Plan & scaffold | this file, repo layout, Makefile, compose with HAPI+Postgres, CI |
| 8–9 Nov | M1 Content & config | rules with verified sources, message library (6 languages), names, districts, clinics, calendar, ClinVar cache |
| 10–11 Nov | M2 Generator + loaders | 20k synthetic people, 24-month history, demo personas, NDJSON → HAPI + DuckDB |
| 12–13 Nov | M3 Care-gap engine + family graph | pure rule evaluator, golden tests, consent-filtered graph, cascade tasks |
| 14–15 Nov | M4 Models, priority, capacity, fairness | Model R/N + isotonic calibration + SHAP, CP-SAT slot fit, fairness floor |
| 16 Nov | M5 Outreach + simulator + evaluation | baseline vs Wiqaya with common random numbers, sensitivity runs, `EVALUATION.md` |
| 17 Nov | M6 API | FastAPI with RBAC, audit, suppression, guest sessions |
| 18 Nov | M7 Web app | Next.js pages, guest flow, Playwright smoke |
| 19 Nov | M8 Docs, polish, deploy | all `docs/`, `make demo`, VPS deploy, submission checklist |
| 20 Nov | Buffer | submit |

Cut order if behind (from the brief): uplift model → CQL export → Synthea → UI sensitivity panel → Leaflet map.
Never cut: consent enforcement, suppression, "Simulated cohort" labels, rule citations, human review, docs.

## Milestones, files and acceptance

### M0 — Plan & scaffold
Files: `PLAN.md`, `README.md`, `Makefile`, `docker-compose.yml`, `.env.example`, `.gitignore`, `pyproject.toml`,
`src/wiqaya/*/__init__.py`, `src/wiqaya/api/app.py` (a `/healthz` stub), `tests/test_smoke.py`,
`.github/workflows/ci.yml`, `docs/DECISIONS.md`, `docker/api.Dockerfile`.
Acceptance: `make up` starts HAPI; `curl localhost:8080/fhir/metadata` returns a CapabilityStatement; `make test` and `make lint` pass.

### M1 — Content & config
- `config/{population,simulation,capacity,calendar,segments}.yaml`. Every numeric value is marked `# ASSUMPTION`.
- `content/rules/*.yaml`: 15 rules. Each `source.url` is fetched by `scripts/verify_sources.py`, which records `retrieved_on` and an HTTP status. Rules that fail are set to `unverified_source`.
- `content/messages/<pathway>/*.yaml`: templates for pathway × audience × channel × language, plus `blocklist.yaml`.
- `content/names/*.yaml`, `content/reference/{districts,clinics_fallback,genes}.yaml`.
- `scripts/fetch_osm_clinics.py` (Overpass; falls back to the YAML) and `scripts/fetch_clinvar.py` (E-utilities; falls back to gene-level entries).
- `src/wiqaya/common/content.py`: Pydantic schemas plus loaders for rules, templates and config.
- `tests/test_messages.py`, `tests/test_content_schema.py`. `make content-check` runs both and `verify_sources --offline`.

### M2 — Generator + loaders
- `generator/`: `households.py`, `people.py`, `family.py`, `latent.py`, `history.py`, `genomics.py`, `consent.py`, `personas.py`, `run.py`.
  - One `numpy.random.Generator` per stage, derived from the config seed with `SeedSequence.spawn`, so the stages don't share random draws.
  - Personas are written first with fixed IDs.
- `fhir/`: `resources.py` (entity → FHIR R4 dict), `ndjson.py`, `client.py` (httpx), `loader.py` (transaction bundles of ≤500 entries; `FHIR_LOAD=sample|full`).
- `store/`: `flatten.py` (entities → Parquet), `duck.py` (DuckDB build), `repo.py` (repository layer for the engines).
- `LatentTruth` goes to a separate Parquet file, `data/parquet/_hidden/latent_truth.parquet`. The repository layer refuses to read it; only `generator` and `evaluate` may.
- `data/runs/<ts>/population_report.md`.
- Tests: determinism (two runs, same seed, same SHA-256 over all NDJSON and Parquet), marginals within tolerance, personas present.

### M3 — Care-gap engine + family graph
- `rules/schema.py`, `rules/snapshot.py` (consent-filtered, field-projected snapshot per rule's `data_required`), `rules/engine.py` (pure evaluator), `rules/run.py` (vectorised pre-filter by age/sex in DuckDB, then the per-person evaluator), `rules/schedules.py`.
- `graph/family.py` (NetworkX graph; an edge is kept only if both people granted `family_links`), `graph/cascade.py`, `graph/household.py`.
- Tests: ≥5 golden cases per rule in `tests/rules/`, plus hypothesis properties (age bounds, consent denial), persona expectations, and a 20k timing test (marked `slow`).

### M4 — Models, priority, capacity, fairness
- `models/features.py` (declares `data_required` per feature; nationality and language are excluded and asserted absent), `models/risk.py`, `models/noshow.py`, `models/calibrate.py`, `models/explain.py` (SHAP → phrases), `models/priority.py`, `models/fairness.py`.
- `capacity/slots.py`, `capacity/fit.py` (CP-SAT; see the scale risk below), `capacity/household.py`.
- Tests: no forbidden features, capacity never exceeded, fairness floor meets `floor_ratio` and logs each adjustment, every due gap stays in the worklist.

### M5 — Outreach, simulator, evaluation
- `outreach/{channel,language,timing,templates,orchestrator,preferences}.py`; `outreach/llm.py` (off by default, with a validator).
- `simulate/{response,policy_baseline,policy_wiqaya,engine,writeback}.py` with common random numbers: each person × week × event key gets its own random draw, shared by both policies.
- `evaluate/{metrics,segments,calibration,report}.py` → `docs/EVALUATION.md`.
- `make simulate`, `make sensitivity`.

### M6 — API
- `api/{app,deps,session,rbac,audit}.py`, `api/routers/{coordinator,planner,family,admin,meta}.py`, `governance/{suppress,genomic_filter,overlay}.py`.
- Signed cookie via `itsdangerous`. A per-session write overlay with a 2-hour TTL. Guest session creation is rate-limited.
- Tests: role matrix, genomic stripping, suppression on every aggregate route (checked by walking all aggregate routes), audit rows written.
- Uplift T-learner only if time allows.

### M7 — Web
- `web/` with Next.js 14 App Router, Tailwind (brief palette), Recharts, react-leaflet with an SVG fallback, SVG family graph.
- Typed client generated with `openapi-typescript` from `/openapi.json`.
- Pages: `/`, `/coordinator`, `/people/[id]`, `/planner`, `/family`, `/admin`, `/about`.
- Playwright smoke in `web/e2e/`.

### M8 — Docs, demo, deploy
- All of §9 in `docs/`, `DEPLOYMENT.md`, Caddy compose override, `make demo`, `make licenses`, `SUBMISSION_CHECKLIST.md`.

## Key design choices (details go in `docs/DECISIONS.md`)

1. **CareGap/Flag in FHIR → `DetectedIssue`.** It is a standard resource with `patient`, `code`, `severity`, `evidence` and `mitigation` (the reviewer decision). A `Basic` resource would need more custom extensions. The rule version is carried in an extension.
2. **HAPI is the system of record, DuckDB is the read model.** The engines never call HAPI, so 20k-person runs stay fast. Person pages read HAPI and fall back to DuckDB.
3. **Python 3.11 pinned via uv** (`.python-version`). This machine's default is 3.14, which some ML wheels (shap, lightgbm) may not support yet.
4. **pnpm via corepack.** pnpm is not installed globally here; `corepack enable` provides it.
5. **The web and api compose services sit behind a profile** until M6/M7, so `make up` in M0 starts only `hapi-db` and `hapi`.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Guideline URLs move, or they block bots | Rules get flagged `unverified_source` | Use a real User-Agent, follow redirects, store the final URL; the Admin UI shows the flag (the brief requires this) |
| Capacity fit too large for CP-SAT (≈3k slots × 20k gaps) | Slow or no solution | Pre-filter by pathway/clinic/distance; solve per week with a rolling horizon; time limit with a greedy fallback, logged |
| Simulator flatters Wiqaya (circularity) | Credibility with judges | Models never see response parameters; common random numbers; 3-way sensitivity analysis reported honestly |
| HAPI bulk load is slow on a laptop | `make demo` > 15 min | Default `FHIR_LOAD=sample` (personas + 2,000); parallel bundle posts; DuckDB path doesn't depend on HAPI |
| Machine-drafted translations (ar/ur/hi/ml/tl) are wrong or awkward | Harm or embarrassment | `review_status: machine_draft` flagged in Admin + docs; English gloss in previews; plain wording |
| Clinical codes guessed wrongly | Governance failure | Only the brief's listed LOINC codes plus codes verified against terminology sites; everything else uses the local code system, listed in `CODES.md` |
| Ramadan/Eid 2027 dates uncertain | Wrong send windows | Verify against a published calendar; label the dates as astronomical estimates |
| Windows dev machine vs Linux CI/VPS | Makefile/path breakage | Makefile uses POSIX shell only (Git Bash here); CI on ubuntu-latest catches drift |
| Fairness floor conflicts with capacity | Floor unreachable | Floor runs before capacity fit as a ranking adjustment; if unmet after fit, reported as such and not hidden |
| Small segments (e.g. Ruwais, Western) | Leaks or noisy metrics | n<11 suppression everywhere; "Model not validated" when held-out n<100 |
| Deployment URL availability | Judges can't access the demo | VPS + Caddy; static fallback screenshots in docs; health check on the deploy |

## Open questions for you

1. **Deployment target:** do you have an Ubuntu VPS and a domain ready for M8, or should I plan for something else (e.g. a temporary tunnel)?
2. **Git remote:** should I create a GitHub repo for CI, or keep it local-only for now? (The repo is initialised locally.)
3. **Deck:** the brief says the visuals and architecture should match "the submission deck". If you have it, drop it in `docs/deck/` so I can align the layer names and workflow steps.
