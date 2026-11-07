# Submission checklist

Future Health Digital Innovation Challenge · Population Health · Challenge 04: Precision Prevention and Screening.
Each criterion maps to the feature, the screen and the document or test that shows it.

## Challenge criteria (1–5)

| # | Criterion | Feature | Screen | Evidence |
|---|---|---|---|---|
| 1 | **Find who is due or overdue** against WCV, immunisation and adult screening schedules, as versioned, auditable rules | 15 YAML rules with cited sources; pure, traced, version-pinned evaluator; `DetectedIssue` output; 20k people in about 10 s | Worklist; gap cards (`rule_id@version`, source, evidence, fields read); Admin → Rule library | `content/rules/`, `src/wiqaya/rules/`, `tests/rules/test_golden.py` (80+ cases), `docs/CODES.md` |
| 2 | **Find hidden higher risk**: family history, genomics, conditions, results, visit history; family-graph cascade with consent | Model R (AUROC 0.78, calibrated); consent-filtered family graph; CASCADE_FH / CASCADE_BRCA clinician tasks; genomic consent gate | Person page (cascade index card, family graph, clinician-only genomic panel) | `src/wiqaya/graph/`, `src/wiqaya/models/`, `docs/MODEL_CARD.md`, `test_gaps_pipeline.py` |
| 3 | **Decide who to contact first**: risk, time sensitivity, no-show; explain every flag; fit capacity; reorder only | Priority score with weights shown; SHAP top-3 phrases; fairness floor (logged); two-stage CP-SAT capacity fit with household bundling and van; guardrail keeps every gap listed | Worklist (bands, slots); person page *Why this rank*; Admin → Model card | `src/wiqaya/models/priority.py`, `fairness.py`, `src/wiqaya/capacity/`, `test_models.py` |
| 4 | **Reach people the right way**: language, channel, timing, household bundles, preference centre | 468 templates (6 languages × pathways × audiences × channels); consented channel order; CHW after 2 non-responses; quiet hours, Eid, Friday, Ramadan rules; bundles; van; opt-out per pathway | Person page message preview (RTL + gloss); Family view and preference centre | `content/messages/`, `src/wiqaya/outreach/`, `src/wiqaya/common/calendar.py`, `test_messages.py`, `test_outreach_sim.py` |
| 5 | **Measure itself**: reach, uptake, timeliness, FP/FN, calibration, yield per segment; n<11 hidden; baseline comparison | 12-week simulator with common random numbers; baseline vs Wiqaya; per-segment metrics with suppression; calibration; sensitivity analysis | Planner console (KPIs, map with hatching, equity table, calibration, sensitivity) | `docs/EVALUATION.md` (auto-generated), `src/wiqaya/evaluate/`, `test_api.py::test_aggregates_are_suppressed` |

## Judging criteria

| Criterion | What to look at |
|---|---|
| **Health impact** | Simulated primary endpoint: **44.6 vs 19.8 completed screenings per 100 contacts**. Gaps closed 21.7% vs 8.0%; missed latent cases 69.5% vs 89.2%; follow-up of abnormal results 21% vs 0%. FH cascade finds carriers through family links. Reported honestly with the reach trade-off and the sensitivity analysis (`docs/EVALUATION.md`). |
| **Technical depth & architecture** | Six-layer architecture with FHIR R4 (HAPI) as system of record and a DuckDB read model (`docs/ARCHITECTURE.md`); rule DSL with field-guarded snapshots; consent-filtered NetworkX graph; LightGBM + isotonic + SHAP; logged fairness floor; OR-Tools CP-SAT; common-random-number simulator; byte-identical determinism; optional agentic AI planner analyst (Claude tool use with audited human-approval gates). |
| **Working demo** | `make demo` from a clean clone (about 10 min); **Continue as Guest** with 5 roles; `docs/DEMO_SCRIPT.md` (3 minutes, pinned personas); Playwright smoke (`make e2e`, 10 tests). |
| **Responsible AI, safety & governance** | `docs/RISKS_AND_SAFEGUARDS.md` (each safeguard linked to code and test); consent per category; genomic stripping; n<11 suppression on every aggregate; audit log; human review with clinician sign-off; model card with prohibited uses; machine-draft translation flags; LLM off by default and fenced; the optional AI planner analyst sees only suppressed aggregates, has its figures checked against the data, and can only propose actions for a human to approve (D-045). |
| **Scalability & deployment readiness** | Public demo on Vercel (web) + one API container; Docker Compose with Caddy (HTTPS, HAPI internal-only); Azure Container Apps (UAE North) pilot path with Malaffi FHIR and Azure Health Data Services (`docs/DEPLOYMENT.md`); CI on GitHub Actions; laptop-scale timings in `docs/ARCHITECTURE.md`. |
| **Commercial viability** | Plugs into existing FHIR (Malaffi) with no rip-and-replace. The value metric is completed visits per 100 contacts, i.e. lower cost per closed gap. The rules and message library are configurable per payer or provider network. Licence-clean stack (`docs/THIRD_PARTY_LICENSES.md`). |

## Hard constraints from the brief

| Constraint | Status | Evidence |
|---|---|---|
| No organiser data; only data we have the right to use; every source declared | ✅ | `docs/DATA_PROVENANCE.md`, Admin → Provenance |
| No real personal data; every person-level record synthetic | ✅ | Generator; `meta.tag` on every resource; `test_every_resource_tagged_simulated` |
| Every metric in the UI labelled **Simulated cohort** | ✅ | Header badge on every page; badge on each KPI card; `label` in every API response; e2e `kpi-simulated` |
| Prototype + documentation with assumptions, dependencies, limitations | ✅ | `docs/ASSUMPTIONS_AND_LIMITATIONS.md`, `docs/DEPENDENCIES.md`, About page |
| Guest access without credentials, all features available | ✅ | Landing → **Continue as Guest** → role picker; role switcher in the header |
| Never diagnoses; reorders outreach only | ✅ | Banner on worklist and person pages; guardrail test `test_every_gap_stays_on_worklist` |

## Documentation set (brief §9)

| File | Status |
|---|---|
| `ARCHITECTURE.md` | ✅ six layers + governance band + eight-step loop (Mermaid) |
| `DATA_PROVENANCE.md` | ✅ |
| `ASSUMPTIONS_AND_LIMITATIONS.md` | ✅ |
| `DEPENDENCIES.md` | ✅ |
| `MODEL_CARD.md` | ✅ |
| `RISKS_AND_SAFEGUARDS.md` | ✅ |
| `THIRD_PARTY_LICENSES.md` | ✅ generated (`make licenses`) |
| `CODES.md` | ✅ generated (`wiqaya docs-codes`) |
| `DECISIONS.md` | ✅ running log |
| `EVALUATION.md` | ✅ generated (`make evaluate`) |
| `DEMO_SCRIPT.md` | ✅ |
| `DEMO_RECORDING_SCRIPT.md` | ✅ extra: narrated video script (8-minute and 3-minute cuts) |
| `SUBMISSION_CHECKLIST.md` | ✅ this file |
| `DEPLOYMENT.md` | ✅ Vercel (web) + container (API) public demo; VPS + Caddy; Azure UAE pilot path |
| `TRANSLATION_REVIEW_NOTES.md` | ✅ extra: native-review priorities |

## Open items before submission
- [ ] Deploy to a public URL with guest access: web on Vercel, API on Railway, Render or Fly.io (`docs/DEPLOYMENT.md`, D-047).
- [x] Push to the team's GitHub repository so CI runs: https://github.com/deepakthanam/wiqaya-hackathon
- [x] AI planner analyst checked against the live Claude API on Haiku (D-046).
- [ ] Line up the visual language and layer names with the final submission deck.
