# Implementation decisions

A running log of small implementation choices (working rule 10). Architecture or scope changes are agreed first.

| # | Date | Decision | Why |
|---|---|---|---|
| D-001 | 2026-11-07 | Pin Python to 3.11 (`.python-version`, `requires-python >=3.11,<3.12`). | The brief specifies 3.11. The machine default is 3.14, which some ML wheels may not support yet. |
| D-002 | 2026-11-07 | Pin HAPI to `hapiproject/hapi:v8.12.0-2` (latest stable tag on 2026-11-07) with `postgres:16-alpine`. | Reproducible builds. The tag can be changed with `HAPI_IMAGE_TAG`. |
| D-003 | 2026-11-07 | Set HAPI `client_id_strategy: ANY`. | Lets the loader use stable client-assigned ids (`demo-001`, `p-000123`) so personas have fixed URLs. |
| D-004 | 2026-11-07 | HAPI port is bound to `127.0.0.1` locally and not published in deployment. | The brief requires HAPI to stay on the internal network only. |
| D-005 | 2026-11-07 | The `api` and `web` compose services sit behind the `app` profile until M6/M7. | `make up` stays fast and only needs the FHIR store in early milestones. |
| D-006 | 2026-11-07 | Represent CareGap/Flag in FHIR as `DetectedIssue`; the rule id@version and priority components go in extensions. | `DetectedIssue` already has patient, code, evidence and mitigation (the reviewer decision); `Basic` would need more custom structure. To be confirmed in M2. |
| D-007 | 2026-11-07 | pytest skips the `slow` and `integration` markers by default; `make test-all` runs them. | Keeps `make test` and CI fast. HAPI-dependent tests run locally. |
| D-008 | 2026-11-07 | pnpm comes from corepack (`corepack enable`) rather than a global install. | pnpm is not installed on the dev machine; corepack ships with Node. |
