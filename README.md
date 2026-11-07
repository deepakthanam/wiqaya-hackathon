# Wiqaya (وقاية): precision prevention and screening

Prototype for the **Future Health Digital Innovation Challenge, Population Health · Challenge 04: Precision Prevention
and Screening** (Abu Dhabi DOH / Hack2skill).

> **Simulated cohort.** Every person-level record in this repository and its deployment is synthetic. There is no real
> personal data, no organiser data and no employer or client data. Wiqaya reorders outreach for care coordinators.
> **It does not diagnose and does not change any clinical pathway.**

Wiqaya:
1. **finds who is due or overdue**, using 15 versioned, cited rules;
2. **finds hidden risk**, using family links with consent, genomic flags and past results;
3. **decides who to contact first**, using calibrated risk, time sensitivity, no-show risk and household bundling, fitted to clinic capacity with a fairness floor, and explains every flag;
4. **reaches people the right way**, choosing language, channel and timing across 6 languages and 4 channels, with household bundles, a mobile van and a preference centre;
5. **measures itself**, comparing against today's baseline with equity metrics, calibration and n<11 suppression.

Optional **AI planner analyst** (Claude, off unless `ANTHROPIC_API_KEY` is set in `.env`): the planner asks questions in plain
English. The agent reads the suppressed aggregate data, runs capacity what-ifs and drafts proposals that a person must approve.
It never sees person-level data, and every figure it quotes is checked against the data it read (`docs/DECISIONS.md` D-045).
It uses Claude Haiku 5.5 by default (`AGENT_MODEL`) and has been checked against the live API (D-046).

Simulated 12-week result (`docs/EVALUATION.md`): **44.6 vs 19.8 completed screenings per 100 contacts** (Wiqaya vs
baseline), with the same capacity and the same random draws. The sensitivity analysis and limitations are reported
honestly in that file.

## Quick start

Prerequisites:
- Python 3.11 via [uv](https://docs.astral.sh/uv/)
- Docker with Compose
- Node 20+ (pnpm via `corepack pnpm`)
- GNU make and a POSIX shell (Git Bash on Windows)

```bash
make demo            # clean clone -> HAPI + synthetic cohort + models + simulation + FHIR load + API + web (about 10 min)
# then open http://localhost:3000 -> Continue as Guest -> pick a role -> follow docs/DEMO_SCRIPT.md
```

Step by step:

```bash
make setup           # Python + web dependencies
make up              # HAPI FHIR + Postgres
make pipeline        # data (20k people) -> gaps -> train/rank/fit -> simulate + sensitivity -> EVALUATION.md
make load            # FHIR sample (personas + ~2,000 people) into HAPI
make api             # http://localhost:8000/api/v1/docs
make web             # http://localhost:3000
make test            # unit, property and API tests
make e2e             # Playwright smoke test
make content-check   # rules, sources and message library (ONLINE=1 re-fetches source URLs)
make help            # everything else
```

## Deploy
The public demo runs the web app on Vercel and the API as one container: free on a Hugging Face Space (`scripts/deploy/hf_space.sh`), or on Railway, Render or Fly.io. See `docs/DEPLOYMENT.md`, which also
covers a single VPS with Docker Compose and the Azure UAE pilot path.

Repository: https://github.com/deepakthanam/wiqaya-hackathon

## Guest access
Click **Continue as Guest** and choose a role. No credentials exist. The role selector in the header switches role and
keeps the same session, so a clinician's sign-off shows up in the family view.

| Role | Sees |
|---|---|
| Coordinator | Worklist, person and household detail, decisions, message previews |
| Clinician | The coordinator's view, plus genomic detail and cascade sign-off |
| Planner | Aggregates only (suppressed): KPIs, map, equity, calibration, sensitivity, optional AI analyst |
| Family | The Al-Hammadi household's messages and the preference centre |
| Admin | Rule library, translations, provenance, model card, audit log, config |

## Architecture
Synthetic generator → FHIR R4 NDJSON → **HAPI FHIR** (system of record) and **DuckDB** (read model) → engines:
- care-gap rules;
- consent-filtered family graph;
- LightGBM + SHAP prioritisation with a fairness floor;
- OR-Tools capacity fit.

From there: outreach orchestrator → consoles (coordinator, planner, family, admin). A governance band of consent, field
guards, RBAC, audit, suppression and human review covers every layer. See `docs/ARCHITECTURE.md`.

## Documentation
- **Architecture and data:** `docs/ARCHITECTURE.md`, `DATA_PROVENANCE.md`, `CODES.md`.
- **Assumptions, risks and models:** `ASSUMPTIONS_AND_LIMITATIONS.md`, `RISKS_AND_SAFEGUARDS.md`, `MODEL_CARD.md`, `EVALUATION.md`.
- **Running and shipping:** `DEPENDENCIES.md`, `DEPLOYMENT.md`, `THIRD_PARTY_LICENSES.md`.
- **Process and submission:** `DECISIONS.md`, `DEMO_SCRIPT.md`, `SUBMISSION_CHECKLIST.md`, `TRANSLATION_REVIEW_NOTES.md`.
- **Plan and brief:** `PLAN.md` and `PROMPT.md`.

## Repository layout
```
config/      population, simulation, capacity, calendar, segments, schedules (every number is an ASSUMPTION)
content/     rules/ (15 YAML), messages/ (468 templates), names/, reference/ (districts, clinics, ClinVar, codes)
src/wiqaya/  generator, fhir, store, rules, graph, models, capacity, outreach, simulate, evaluate, governance, api
web/         Next.js 14 consoles + Playwright smoke test
scripts/     source verification, OSM/ClinVar fetch, licences, demo, e2e
tests/       golden rule cases, hypothesis properties, determinism, models, API permissions
```
