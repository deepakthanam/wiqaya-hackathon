# Architecture

Wiqaya is a population-health layer that runs beside the clinical record. It reads FHIR, finds care gaps with
versioned rules, finds hidden risk through family links and past results, ranks outreach to fit real capacity, and
measures its own equity. **It only reorders outreach. It never diagnoses or changes a clinical pathway.**

## Six layers, with a governance band

```mermaid
flowchart TB
  subgraph L1["1 · Data sources"]
    G["Synthetic generator<br/>(household-first, seeded)"]
    S["Synthea (optional)"]
    M["Malaffi FHIR feed<br/>(pilot path)"]
    R["Reference: guidelines, ClinVar,<br/>OSM, holidays, codes"]
  end
  subgraph L2["2 · Ingest & consent"]
    N["FHIR R4 NDJSON"]
    C["Consent per category<br/>(clinical, family links, genomic, channels)"]
    L["Loader A: transaction bundles ≤500<br/>Loader B: NDJSON → Parquet → DuckDB"]
  end
  subgraph L3["3 · FHIR store"]
    H["HAPI FHIR JPA (Postgres)<br/>system of record"]
    D["DuckDB read model<br/>(derived, analytics)"]
  end
  subgraph L4["4 · Engines"]
    E1["Care-gap engine<br/>15 YAML rules, pure + traced"]
    E2["Family graph<br/>consent-filtered cascade"]
    E3["Prioritisation<br/>Model R/N + SHAP + fairness floor"]
    E4["Capacity fit<br/>OR-Tools CP-SAT"]
  end
  subgraph L5["5 · Outreach"]
    O["Channel · language · timing<br/>468 templates, 6 languages<br/>household bundles, mobile van"]
  end
  subgraph L6["6 · Consoles"]
    U1["Coordinator worklist + person view"]
    U2["Planner equity console"]
    U3["Family view + preference centre"]
    U4["Admin: rules, provenance, audit"]
  end
  G & S & M --> N --> C --> L --> H & D
  R --> E1 & O
  D --> E1 --> E2 --> E3 --> E4 --> O --> U3
  H --> U1
  E3 --> U1 & U2
  subgraph GOV["Governance band (applies to every layer)"]
    direction LR
    g1["Consent filtering"] --- g2["data_required field guard"] --- g3["RBAC + audit"] --- g4["n<11 suppression"] --- g5["Genomic stripping"] --- g6["Human review gate"] --- g7["Simulated-cohort labels"]
  end
  L6 -.-> GOV
```

## The eight-step loop (human gate at step 5)

```mermaid
flowchart LR
  s1["1 Ingest<br/>FHIR + consent"] --> s2["2 Detect gaps<br/>versioned rules"]
  s2 --> s3["3 Hidden risk<br/>family graph, models"]
  s3 --> s4["4 Prioritise & fit<br/>capacity, fairness floor"]
  s4 --> s5{{"5 HUMAN REVIEW<br/>coordinator accept / change / reject<br/>clinician sign-off for cascade"}}
  s5 --> s6["6 Reach out<br/>channel, language, timing, bundles"]
  s6 --> s7["7 Visit & record<br/>results written back as FHIR"]
  s7 --> s8["8 Measure<br/>uptake, FP/FN, calibration, equity"]
  s8 --> s1
  style s5 fill:#F6E6E1,stroke:#B5543F,stroke-width:2px
```

## Components and where they live

| Layer | Component | Code |
|---|---|---|
| Data | Synthetic generator (households, people, family, latent truth, 24-month history, consent, personas) | `src/wiqaya/generator/` |
| Data | FHIR R4 mapping, NDJSON, HAPI loader (sample / full) | `src/wiqaya/fhir/` |
| Store | NDJSON → Parquet → DuckDB; repository layer; hidden-truth guard | `src/wiqaya/store/` |
| Engine | Rule schema, pure evaluator, field-guarded snapshots, bulk runner | `src/wiqaya/rules/` |
| Engine | Consent-filtered family graph, cascade links | `src/wiqaya/graph/` |
| Engine | Features, LightGBM + isotonic, SHAP phrases, priority, fairness floor | `src/wiqaya/models/` |
| Engine | Slot supply, two-stage CP-SAT fit, household bundling | `src/wiqaya/capacity/` |
| Outreach | Library + validator, contact planning, rendering, timing, orchestrator | `src/wiqaya/outreach/`, `src/wiqaya/common/calendar.py` |
| Evaluation | 12-week simulator (common random numbers), metrics, report | `src/wiqaya/simulate/`, `src/wiqaya/evaluate/` |
| Governance | Suppression, overlays, audit, provenance register | `src/wiqaya/governance/` |
| API | FastAPI `/api/v1`, guest sessions, RBAC | `src/wiqaya/api/` |
| Web | Next.js 14 consoles | `web/` |

## Data flow and stores

- **FHIR is the system of record.** HAPI FHIR (R4, Postgres) holds every resource type:
  - `Patient`, `Group` (household), `RelatedPerson`, `Encounter`, `Appointment` (no-shows), `Observation` (BP as LOINC 85354-9 panels; genomic findings as LOINC 69548-6), `Condition`, `Immunization`, `FamilyMemberHistory`, `Consent` (one per category), `Communication`, `Organization`/`Location` (generic clinics, van stops) and `DetectedIssue` (care gaps).
  - The default `FHIR_LOAD=sample` loads the demo personas plus about 2,000 people. `FHIR_LOAD=full` loads everyone.
- **DuckDB is the derived read model.** It is flattened from the same NDJSON. The engines only read DuckDB, through `store/repo.py`.
- **Person pages read HAPI first.** If HAPI is down or the person is not in the sample, they fall back to DuckDB and show a banner.
- **Hidden ground truth** (`data/hidden/latent_truth.parquet`) is readable only by the generator, the simulator and the evaluator. `repo.load_latent` enforces this.
- **Pilot path:** loader A is replaced by a Malaffi FHIR read through the same client. The engines do not change.

## Determinism

One seed per stage (`numpy.random.SeedSequence.spawn`). CP-SAT runs with one worker and a deterministic time budget,
and the simulator's random draws come from SHA-256 hashes. The same seed produces byte-identical NDJSON and Parquet
(`tests/test_generator.py`) and the same capacity plan.

## Scale

On a laptop: 20,000 people are generated in about 35 s and gaps for all 20k are evaluated in about 10 s. Training,
ranking and capacity fit take about 2.5 min. The simulation with sensitivity analysis takes about 3 min.

What changes in production:
- DuckDB becomes a warehouse.
- Rules are evaluated incrementally, per changed patient (FHIR Subscription).
- CP-SAT runs per clinic cluster. It is already decomposed by site cluster.
