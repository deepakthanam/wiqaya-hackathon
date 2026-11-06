# Wiqaya (وقاية) — precision prevention and screening

Prototype for the Future Health Digital Innovation Challenge, Population Health · Challenge 04
(Abu Dhabi DOH / Hack2skill).

> **Simulated cohort.** Every person-level record in this repository and its deployment is synthetic.
> There is no real personal data, no organiser data and no employer or client data.
> Wiqaya reorders outreach for care coordinators. **It does not diagnose and does not change any clinical pathway.**

Status: Milestone 0 (scaffold). See `PLAN.md` for the build plan and `PROMPT.md` for the full brief.

## Quick start

Prerequisites: Python 3.11 via [uv](https://docs.astral.sh/uv/), Docker with Compose, GNU make, and a POSIX shell
(on Windows, use Git Bash). Node 20+ with pnpm (`corepack enable`) is needed from Milestone 7.

```bash
make setup         # create .env, install Python deps
make up            # start HAPI FHIR + Postgres, wait for /fhir/metadata
make fhir-metadata # prints: CapabilityStatement 4.0.1 HAPI FHIR Server ...
make test          # unit tests
make help          # all targets (pipeline targets are stubs until their milestone)
```

## Architecture (summary)

Synthetic generator → FHIR R4 NDJSON → **HAPI FHIR** (system of record) and **DuckDB** (analytics read model) →
engines (care-gap rules, family graph, prioritisation, capacity fit) → outreach orchestrator → consoles
(coordinator, planner, family, admin). A governance layer covers consent, small-cell suppression, audit and
role-based access. Full details will be in `docs/ARCHITECTURE.md`.

## Guest access

The web app (Milestone 7) has a **Continue as Guest** button with a role picker: coordinator, planner, family or admin.
No credentials are needed.
