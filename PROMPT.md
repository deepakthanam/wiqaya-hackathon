# Wiqaya: Claude Code build brief

> **How to use this file**
> 1. Create an empty folder, e.g. `wiqaya/`, and put this file in it as `PROMPT.md`.
> 2. Prerequisites on your machine: Python 3.11+, `uv`, Node 20+, `pnpm`, Docker + Docker Compose, Git. Java 17 only if you enable the optional Synthea path.
> 3. Start Claude Code in that folder and say:
>    `Read PROMPT.md fully. Follow "Working rules". Start with Milestone 0 and stop at its checkpoint.`
> 4. After each checkpoint, review and say `continue to Milestone N`.

---

## 0. Mission

You are building **Wiqaya** (وقاية, "prevention"), a working prototype for the **Future Health Digital Innovation Challenge, Population Health · Challenge 04: Precision Prevention and Screening** (Abu Dhabi DOH / Hack2skill). The prototype and its documentation are due **20 November 2026**.

**What Wiqaya does.** It is a population-health platform for care coordinators and health authorities that:

1. **Finds who is due or overdue.** It runs every person's longitudinal record against approved Well-Child Visit (WCV), immunisation and adult screening schedules, encoded as versioned, auditable rules.
2. **Finds hidden higher risk.** It uses family history, genomic flags, chronic conditions, past results and visit history. A **family graph** triggers guideline-backed cascade screening of relatives, with consent.
3. **Decides who to contact first.** It ranks people by clinical risk, time sensitivity and no-show likelihood, explains every flag (rule and guideline version, plus the top-3 SHAP drivers), and fits the list to real clinic capacity. **It only reorders outreach. It never diagnoses or changes a clinical pathway.**
4. **Reaches people the right way.** It chooses language, channel and timing, bundles households into one visit day, and gives people a preference centre with opt-out per pathway.
5. **Measures itself.** An equity and outcomes console shows reach, uptake, timeliness, FP/FN, calibration and clinical yield per population segment, hides cells with n < 11, and compares against today's age/gender-rule baseline.

**Hard constraints from the challenge:**
- The organisers provide **no data**. Use only data we have the legal right to use, declare every source, and use **no real personal data**. Every person-level record is synthetic.
- Every metric shown in the UI must carry a visible **"Simulated cohort"** label.
- The submission needs a working prototype plus technical documentation with explicit **assumptions, dependencies and limitations**.
- Judges must be able to use the app without credentials, through a **"Continue as Guest"** button with all features available.
- Judging criteria:
  - Health impact
  - Technical depth and architecture
  - Working demo
  - Responsible AI, safety and data governance
  - Scalability and deployment readiness
  - Commercial viability

---

## 1. Working rules for Claude Code

1. **Plan first.** In Milestone 0, write `PLAN.md` (milestones, files, risks), then stop for approval.
2. **Work milestone by milestone.** Commit after each, using conventional commit messages. Don't start the next milestone until the current one's acceptance checks pass.
3. **Determinism.** Every random process takes a seed from `config/`. The same seed must produce byte-identical outputs. Test this.
4. **Never invent clinical codes.** Use LOINC/SNOMED/CVX codes only when you are certain of them. Otherwise use the local code system `http://wiqaya.health/CodeSystem/local` and list it in `docs/CODES.md`.
5. **Never invent guideline facts.** Each rule's `source` must name the guideline, year and URL. Fetch the URL to verify it exists, and record `retrieved_on`. If you cannot verify a source, mark the rule `status: unverified_source` and surface it in the Admin UI.
6. **All rules are demo encodings.** Every rule carries `status: demo_encoding_requires_clinical_validation`.
7. **No real people or organisations.** Names are synthetic, from per-nationality name lists you create. Clinics use generic names ("Primary Care Centre – Khalifa City"), never real facility brands. Real place names (districts) are fine.
8. **Privacy by construction.**
   - The engines read only the fields each rule or model declares in `data_required`.
   - Genomic findings are visible only to the Clinician/Admin roles.
   - Relatives are never told an index patient's diagnosis.
9. **LLM use is optional and fenced.** The default build uses **deterministic templating** and no LLM. If `LLM_ENABLED=true`, the LLM may only:
   - fill slots in pre-approved templates;
   - paraphrase a flag's reasons into plain language from structured inputs.

   Its output is validated: no new numbers, no diagnosis words from a blocklist, and length limits. If validation fails, fall back to the deterministic text. Never send it free text containing health data beyond the slot values.
10. **Ask before deviating** from this brief on architecture or scope. Make small implementation choices yourself and log them in `docs/DECISIONS.md`.
11. **Keep it runnable on a laptop.** `make demo` should work on 16 GB RAM in under 15 minutes from a clean clone, excluding Docker image pulls.

---

## 2. Stack and repo layout

| Concern | Choice |
|---|---|
| Language (backend, data, ML) | Python 3.11, managed with `uv` |
| FHIR system of record | HAPI FHIR JPA server (Docker image `hapiproject/hapi`, Postgres backend), FHIR R4 |
| Analytics read model | DuckDB + Parquet, derived from the same FHIR NDJSON |
| Rules | YAML rule definitions + Python evaluator (`wiqaya.rules`); CQL export is a stretch goal |
| Graph | NetworkX |
| ML | LightGBM, scikit-learn (calibration, metrics), SHAP |
| Capacity optimisation | Google OR-Tools (CP-SAT or linear solver) |
| API | FastAPI + Pydantic v2, served by Uvicorn |
| Web | Next.js 14 (App Router, TypeScript), Tailwind, Recharts, Leaflet with OSM tiles and attribution, `react-force-graph-2d` or SVG for the family graph |
| Tests | pytest, hypothesis (rule properties), Playwright (UI smoke) |
| Orchestration | `docker-compose.yml` with services `hapi-db`, `hapi`, `api`, `web`; a `Makefile` at the root |

```
wiqaya/
  PROMPT.md  PLAN.md  README.md  Makefile  docker-compose.yml  .env.example
  config/
    population.yaml        # demographic shares, prevalence, behaviour params (ASSUMPTIONS, cited)
    simulation.yaml        # history period, evaluation period, response-model params, seeds
    capacity.yaml          # clinics, slots per pathway per day, mobile van schedule
    calendar.yaml          # Ramadan, Eid, school terms, summer heat (verify dates)
    segments.yaml          # segment definitions used by the equity console
  content/
    rules/                 # one YAML per guideline rule (see §5.1)
    messages/              # templates per pathway × audience × channel × language (see §5.2)
    names/                 # synthetic first/family name lists per nationality group
    reference/
      districts.yaml       # Abu Dhabi emirate districts with centroid lat/lon and region
      clinics_fallback.yaml
      genes.yaml           # gene → condition → cascade rule mapping
      clinvar_cache.json   # produced by scripts/fetch_clinvar.py, committed
      osm_clinics.geojson  # produced by scripts/fetch_osm_clinics.py, committed if fetched
  src/wiqaya/
    generator/  fhir/  store/  rules/  graph/  models/  capacity/  outreach/  simulate/
    evaluate/  governance/  api/  common/
  web/                     # Next.js app
  scripts/                 # fetch_clinvar.py, fetch_osm_clinics.py, fetch_synthea.sh (optional)
  data/                    # gitignored outputs: ndjson/, parquet/, duckdb/, runs/
  docs/                    # see §9
  tests/
```

---

## 3. Data model

### 3.1 Canonical entities (Python dataclasses / Pydantic, mirrored in DuckDB)

**People and households**
- `Household(id, district_id, housing_type{villa,apartment,labour_accommodation}, primary_language, size)`
- `Person(id, household_id, given, family, sex, birth_date, nationality_group, preferred_language, literacy_proxy{low,med,high}, phone_type{smartphone,basic,none}, insurance_tier{Thiqa,Enhanced,Basic}, district_id, has_regular_clinic, assigned_clinic_id)`
- `Relationship(person_id, related_person_id, type{mother,father,child,sibling,spouse,grandparent,aunt_uncle,cousin}, degree{1,2,3})`. Relatives do not have to live in the same household; siblings of adults can live elsewhere.

**Clinical record**
- `Encounter(id, person_id, date, type{wcv,adult_screen,acute,chronic_review,mobile_van}, clinic_id, attended{bool}, scheduled_via{walk_in,invite_baseline,invite_wiqaya,self})`
- `Observation(id, person_id, date, code, value, unit)`. Covers BMI, BMI-for-age percentile, BP, HbA1c, LDL, total cholesterol, developmental screen result, autism screen result, Pap/HPV result, FIT result, mammogram BI-RADS category.
- `Condition(id, person_id, code, onset_date, verification{confirmed,suspected})`
- `Immunization(id, person_id, vaccine_code, date)`
- `FamilyHistory(person_id, relative_type, condition_code, onset_age)`
- `GenomicFinding(person_id, gene, variant_ref, classification{pathogenic,likely_pathogenic}, source{genome_programme_sim})`

**Consent and contact**
- `Consent(person_id, category{clinical_data,family_links,genomic,contact_sms,contact_whatsapp,contact_call,chw_visit}, status{granted,denied,not_asked}, date)`
- `ContactPreference(person_id, channel_order[], quiet_hours, pathway_opt_outs[], remind_later_until)`

**Outputs**
- `CareGap(id, person_id, rule_id, rule_version, status{due,overdue,missed,eligible_early,followup_overdue}, due_date, days_overdue, evidence{field: value}[], created_at)`
- `Flag(id, person_id, gaps[], priority_score, components{risk,time_sensitivity,no_show}, shap_top3[], rank, slot_assignment, reviewer_decision{pending,accepted,changed,rejected}, reviewer_note)`
- `Communication(id, person_id, household_id, template_id, language, channel, sent_at, response{booked,declined,later,none}, simulated=True)`
- `AuditEvent(ts, actor_role, action, entity, entity_id, fields_read[])`

**Hidden ground truth.** This table is **never exposed to models or the API.** Only the generator and the evaluator see it.
- `LatentTruth(person_id, undiagnosed_t2d, prediabetes, dyslipidaemia, hypertension, fh_carrier, developmental_delay, cervical_cin2plus, colorectal_advanced_neoplasia, response_propensity_by_channel{}, language_sensitivity, distance_sensitivity, bundle_effect)`

### 3.2 FHIR R4 mapping

| Entity | FHIR resource |
|---|---|
| Person | `Patient` |
| Relationship | `RelatedPerson`, with `relationship` from the v3-RoleCode family-member codes (e.g. `MTH`, `FTH`, `CHILD`, `SIB`, `SPS`). Verify each code before use. |
| Encounter | `Encounter` |
| Observation | `Observation` |
| Condition | `Condition` |
| Immunization | `Immunization` |
| FamilyHistory | `FamilyMemberHistory` |
| GenomicFinding | `Observation`, LOINC `69548-6` "Genetic variant assessment", with components for gene studied (`48018-6`) and variant. Follow the HL7 Genomics Reporting IG loosely and record that in `docs/CODES.md`. |
| Consent | `Consent`, one per category |
| Communication | `Communication` |
| Appointment | `Appointment` |
| CareGap / Flag | `DetectedIssue`, or local `Basic` with an extension. Choose one and document it. |

**Codes known to be correct** (use them):

| Measure | LOINC |
|---|---|
| HbA1c | `4548-4` |
| BMI | `39156-5` |
| Systolic BP | `8480-6` |
| Diastolic BP | `8462-4` |
| BP panel | `85354-9` |
| LDL (calculated) | `13457-7` |

For anything else you are unsure of, use local codes.

### 3.3 Storage flow

```
generator → data/ndjson/*.ndjson (FHIR R4, one file per resource type)
          → loader A: HAPI FHIR via transaction bundles of ≤500 entries
            (FHIR_LOAD=sample: all demo personas + 2,000 random people [default];
             FHIR_LOAD=full: everyone)
          → loader B: flatten to Parquet → DuckDB (data/duckdb/wiqaya.duckdb)
engines read DuckDB through a repository layer; person/household detail pages read HAPI
(fall back to DuckDB if HAPI is down, and show a banner saying so).
```

FHIR is the system of record. DuckDB is a derived read model. In a pilot, loader A is replaced by a read from Malaffi through the same FHIR client.

---

## 4. Synthetic population generator (`src/wiqaya/generator/`)

Produce a population of `N=20,000` people (configurable) using a **household-first** process:

1. **Households.**
   - Sample district and housing type from `population.yaml`.
   - Labour-accommodation households are mostly single working-age men from South Asian nationality groups, 4–12 per unit, concentrated in Musaffah and industrial districts.
   - Family households get 1–2 adults plus 0–5 children, plus a grandparent with configured probability (higher for Emirati households).
2. **People.**
   - Assign age, sex, nationality group, language, literacy proxy, phone type, insurance tier (Thiqa mostly Emirati; Basic mostly labour accommodation), assigned clinic and regular-clinic flag.
   - Names come from `content/names/`.
3. **Extended family.**
   - Create siblings of adults living in other households. Target about 30% of adults with at least one sibling in the cohort.
   - Create grandparent links. Use a configurable consanguinity share among Emirati marriages to raise recessive-carrier co-occurrence. This is a modelling assumption, documented as such.
4. **Latent truth.**
   - Draw conditions using logistic models in `population.yaml`, driven by age, sex, BMI, nationality group and family history.
   - FH carrier status is inherited: a first-degree relative of a carrier carries with probability 0.5.
   - Developmental delay is drawn for children under 6.
5. **History period.** Simulate the 24 months before `T0 = 2026-11-01`:
   - WCV attendance by schedule with missed-visit probability from behaviour parameters;
   - immunisations;
   - adult screening encounters, with lab values generated from latent truth plus measurement noise;
   - diagnoses when a screen detects a latent condition (using configured test sensitivity);
   - acute visits;
   - invitations under the **baseline policy** (age/gender rules, generic SMS in Arabic or English) and responses from the response model.

   This history is what the models train on.
6. **Genomic findings.** About 1–2% of the cohort have a simulated "genome programme" result:
   - FH genes `LDLR`, `APOB`, `PCSK9` for carriers;
   - `BRCA1`/`BRCA2` at a low configured rate;
   - `HBB` carrier status.

   Variant references come from `clinvar_cache.json`. They are illustrative only and must be labelled that way.
7. **Consent.**
   - clinical_data: granted for about 97%;
   - family_links: about 80%;
   - genomic: about 70% of those with findings;
   - contact channels by phone type;
   - a small share of `denied` in every category, so consent enforcement is visible.
8. **Pinned demo personas.** Fixed IDs, seeded first; see §11.

**`config/population.yaml`.** Every numeric default in this file is a **placeholder assumption**:
- Put a comment beside each value: `# ASSUMPTION – replace with SCAD/DOH published figure; cite in DATA_PROVENANCE.md`.
- Starting nationality mix: Emirati 0.20, Indian 0.30, Pakistani 0.12, Bangladeshi 0.07, Filipino 0.07, Other Arab 0.12, Western 0.04, Other 0.08.
- Districts in `content/reference/districts.yaml`, with approximate centroids. Verify each centroid against OSM and record it:
  - Abu Dhabi Island, Al Reem Island, Khalifa City, Mohammed Bin Zayed City, Musaffah, Al Shamkha, Yas Island (Abu Dhabi region)
  - Al Ain City, Al Hili (Al Ain region)
  - Madinat Zayed, Ruwais, Ghayathi (Al Dhafra region)

**Optional Synthea path** (`scripts/fetch_synthea.sh`, `make synthea`):
- Download the Synthea release jar, generate N patients and convert them with the same FHIR loader.
- A `localise` step remaps demographics to the Abu Dhabi config and assembles Synthea patients into households by age compatibility.
- Ground-truth evaluation is only available on the native generator, which is the default. Document this trade-off in `docs/DECISIONS.md`.

**Acceptance**
- `make data SEED=42 N=20000` finishes in under 5 minutes.
- A summary report (`data/runs/<ts>/population_report.md`) shows:
  - marginals vs config;
  - household size distribution;
  - prevalence of each latent condition;
  - % with at least one overdue gap;
  - consent shares.
- Re-running with the same seed gives an identical hash.

---

## 5. Content to create

### 5.1 Guideline rules (`content/rules/*.yaml`)

Rule schema:

```yaml
id: ADULT_T2D_SCREEN
version: 1.0.0
title: Prediabetes and type 2 diabetes screening
pathway: adult_screening            # wcv | immunisation | developmental | adult_screening | followup | cascade
status: demo_encoding_requires_clinical_validation
source:
  name: "USPSTF – Screening for Prediabetes and Type 2 Diabetes"
  year: 2021
  url: "<verify and fill>"
  retrieved_on: "<YYYY-MM-DD>"
  licence: "US Government work – public domain"
applies_to:
  age_years: {min: 35, max: 70}
  any_of:
    - bmi_min: 25
  exclude_conditions: [t2d, t1d]
interval_months: 36
eligible_early:
  - reason: "Family history of type 2 diabetes (guideline allows earlier screening)"
    when: {family_history_any: [t2d]}
    age_years: {min: 25}          # ASSUMPTION – clinical reviewer to confirm
data_required: [birth_date, bmi_latest, conditions, family_history, obs:hba1c]
satisfied_by: [obs:hba1c]
output_codes: {gap_code: "local:gap-t2d-screen"}
```

Create these rules. Each one needs at least 5 golden test cases in `tests/rules/` (due, not due, overdue, excluded, eligible early or follow-up).

| Rule ID | Content | Notes |
|---|---|---|
| `WCV_SCHEDULE` | Well-Child Visits at newborn, 1, 2, 4, 6, 9, 12, 15, 18, 24, 30 months, then yearly to 18 | The schedule lives in `config` so DOH's schedule can replace it. Mark the source "configurable; default follows a common periodicity schedule; replace with DOH WCV schedule". |
| `DEV_SCREEN` | Developmental screening at 9, 18, 30 months | |
| `AUTISM_SCREEN` | Autism screening at 18 and 24 months | |
| `IMMUNISATION_CATCHUP` | Due/overdue doses against a schedule table in config | Mark the schedule as a placeholder to be replaced with the UAE national schedule. |
| `CHILD_BMI_FOLLOWUP` | BMI-for-age ≥ 95th percentile with no follow-up encounter in 6 months | Uses a local code. |
| `ADULT_T2D_SCREEN` | As in the example above | |
| `ADULT_BP_SCREEN` | Adults 18+ | |
| `ADULT_LIPID_CVD` | Lipid assessment, adults 40–75, for CVD risk | |
| `CERVICAL_SCREEN` | Ages 21–65; interval by test type | |
| `COLORECTAL_SCREEN` | Ages 45–75 | |
| `BREAST_SCREEN` | Ages 40–74, every 2 years | |
| `FOLLOWUP_PREDIABETES` | HbA1c 5.7–6.4% with no retest in 12 months | |
| `FOLLOWUP_BP_ELEVATED` | Elevated BP reading with no recheck within the configured window | |
| `CASCADE_FH` | First-degree relatives of an index person with an FH pathogenic finding or confirmed FH diagnosis; children from the configured age | Source: NICE CG71, *Familial hypercholesterolaemia: identification and management*. **Never auto-contacts.** It creates a clinician task, and outreach is only allowed after clinician approval and index-patient consent to share. |
| `CASCADE_BRCA` | Clinician-only task, with no outreach templates | Genetic counselling referral. |

The evaluator in `src/wiqaya/rules/engine.py` must be:
- **pure:** person snapshot + rule + as-of date → `CareGap | None`;
- **traced:** it emits `evidence` and `fields_read`;
- **version-pinned:** each gap stores `rule_id@version`.

Stretch goal: `rules export-cql` writes a CQL library per rule for audit, marked "not executed".

### 5.2 Outreach message library (`content/messages/`)

Template schema:

```yaml
id: WCV_DUE_PARENT_WHATSAPP
pathway: wcv
audience: parent            # parent | adult | caregiver_of_elder | teen
channel: whatsapp           # whatsapp | sms | call_script | chw_script
language: en                # ar | en | ur | hi | ml | tl
review_status: source       # source (English, human-written) | machine_draft | native_reviewed
max_chars: 600
slots: [recipient_first_name, child_first_name, visit_label, clinic_name, slot_options]
text: >
  Hello {recipient_first_name}, this is {clinic_name}. {child_first_name} is due for a routine
  check-up ({visit_label}). We have kept times for you: {slot_options}.
  Reply 1 to book, 2 for another time, 3 if you prefer not to receive these reminders.
```

**Pathways and audiences to cover:**
- WCV due or overdue
- Developmental check
- Immunisation catch-up
- Adult screening, one template per screen
- Follow-up retest
- Household bundle ("{n} family members can be seen on one day")
- Mobile van visit
- Cascade, **clinician-approved only**: generic wording only, e.g. "Your doctor recommends a heart-health check for your family." It must **never** name the relative or their condition.
- Preference confirmation, opt-out confirmation and remind-later confirmation

**Channels:**
- WhatsApp: about 600 characters maximum.
- SMS: 160 characters for Latin script, or 70 per segment for Arabic/Indic scripts. Keep SMS to at most 2 segments.
- Call scripts and community health worker (CHW) scripts.

**Languages:** ar, en, ur, hi, ml, tl.
- You write English as `source`.
- Other languages are `machine_draft` and must be flagged in the Admin UI and in `docs/ASSUMPTIONS_AND_LIMITATIONS.md` as needing native-speaker review.
- Arabic is Modern Standard Arabic and respectful in register. Plain language at roughly a 6th-grade level.

**Rules enforced by `tests/test_messages.py`:**
- Every template exists for every language in its pathway.
- Every slot used in `text` is declared.
- Length limits are respected.
- Text matches no word in `content/messages/blocklist.yaml` (diagnosis words, fear language, guilt language).
- Every template carries a decline option.

### 5.3 Calendar and cultural timing (`config/calendar.yaml`)

- Ramadan 2027 (approximately 8 Feb – 9 Mar 2027; **verify**): no appointment invites during fasting daytime hours for adults who fast. Prefer evening slots and send messages after iftar.
- Eid holidays: no sends.
- Friday midday: no sends.
- Quiet hours: 21:00–08:00.
- School exam windows (placeholder dates): avoid teen and child appointments.
- Summer heat (Jun–Sep): prefer indoor and mall-adjacent clinics, and avoid midday mobile-van slots.

### 5.4 Clinics and capacity

- `scripts/fetch_osm_clinics.py` queries the Overpass API for `amenity=clinic|doctors|hospital` within the Abu Dhabi emirate bounding box and saves GeoJSON with OSM attribution.
- If the network is blocked, use `clinics_fallback.yaml`: 2–4 generic clinics per district at approximate coordinates, named generically.
- `config/capacity.yaml` sets per-clinic slots per pathway per weekday. A mobile van visits Musaffah and Al Dhafra districts on configured days.
- Total weekly capacity must be **well below** total due gaps, so prioritisation matters. Default: capacity of about 15% of open gaps over the 12-week evaluation.

### 5.5 ClinVar reference (`scripts/fetch_clinvar.py`)

- Use NCBI E-utilities to fetch a handful of pathogenic variant records per gene (LDLR, APOB, PCSK9, BRCA1, BRCA2, HBB). **Check the query syntax against the current NCBI E-utilities/ClinVar documentation before use.**
- Store `{gene, variation_id, name, clinical_significance}` in `clinvar_cache.json` with retrieval date.
- If the fetch fails, fall back to gene-level entries with `variation_id: null`, and the app shows "illustrative variant".

---

## 6. Engines

### 6.1 Care-gap engine (`wiqaya.rules`)

- `run_gaps(as_of=T0)` evaluates all rules for all people, using consent-filtered snapshots.
- People with `clinical_data` consent denied get no gaps. Count them in an "excluded by consent" metric.
- Output goes to the `care_gaps` table.
- Performance: 20k people × 15 rules in under 60 s.

### 6.2 Family graph (`wiqaya.graph`)

- Build a NetworkX graph from `Relationship`, keeping only edges where **both** endpoints granted `family_links`.
- Cascade rules walk degree-1 neighbours of index persons and create `CASCADE_*` gaps as **clinician tasks** (`requires_clinician=True`).
- Household view: everyone in a household with open gaps, plus suggested bundle days where clinic capacity allows.

### 6.3 Prioritisation (`wiqaya.models`)

Train on the history period only. Evaluate on a held-out set of people.

**Model R: clinical risk elevation**
- **Label:** a condition detected within 12 months *after* a screening encounter in history. Use observed outcomes only. Never use latent truth or cost as the label.
- **Features:** age, sex, BMI and its trend, last lab values and trends, conditions count, family history flags, genomic flag (only if `genomic` consent is granted), missed visits, district deprivation proxy, months since last screen.
- **Excluded:** nationality group and language. Nationality, language, district and insurance tier are used only as **monitoring segments**, so the console can show they are not driving outcomes.
- Calibrate with isotonic regression on a validation split.

**Model N: no-show propensity**
- Label: past invitations not attended.
- Features: past attendance, distance to the assigned clinic, phone type, channel used, language match of the past message, household size, housing type.

**Priority score** (weights in config, shown in the UI):

```
priority = w_r · risk_calibrated
         + w_t · time_sensitivity
         + w_n · no_show_risk          # w_n > 0: invest more effort in hard-to-reach people
         + w_h · household_bundle_bonus
```

- `time_sensitivity` comes from the rule: developmental and early-childhood items, follow-ups of abnormal results and overdue-by-more-than-90-days are high.
- **Guardrail:** every guideline-due gap stays in the worklist. The score changes **order and outreach intensity only**.

**Explanations**
- SHAP TreeExplainer gives the top-3 drivers per person, rendered as plain phrases from a feature → phrase dictionary, e.g. "BMI rising over 2 years", "2 missed Well-Child Visits".
- The rule citation is always shown first.

**Fairness floor**
- After ranking, check each monitoring segment's share of slots against its **need-adjusted share** (its share of open high-time-sensitivity gaps).
- If a segment falls below `floor_ratio` (default 0.8), up-rank its next-highest-priority items until it meets the floor.
- Log every adjustment.

### 6.4 Capacity fit (`wiqaya.capacity`)

- Assign people to slots over the 12-week horizon with OR-Tools.
- Objective: maximise Σ priority × P(attend | slot).
- Constraints:
  - slot capacity;
  - pathway match;
  - a travel-distance limit by phone type and housing type;
  - calendar rules;
  - household members on the same day where possible (soft constraint, bonus weight).
- Output: an assigned slot and outreach plan per flag.

### 6.5 Outreach orchestrator (`wiqaya.outreach`)

**Channel order**
- Use the consented channels by default.
- Labour accommodation with no WhatsApp: SMS, plus a CHW visit after 2 non-responses.
- Elderly person with a caregiver: caregiver audience.

**Language:** the person's `preferred_language`; for minors, the parent's.

**Timing:** apply calendar and quiet-hours rules.

**Template:** pick by pathway, audience, channel and language, then fill the slots.

**Uplift model** (Milestone 6, stretch but planned)
- A T-learner on history, where some people were randomly invited in the generator's history period.
- Used to choose between "message only" and "message + call/CHW" for people with low predicted uplift from a message.

**Preference centre:** opt-out per pathway, channel order and remind-later. A decline-with-reason stops further outreach for that pathway.

### 6.6 Simulator (`wiqaya.simulate`)

- Simulate the 12-week evaluation period from T0 under two policies with **common random numbers**:
  - **Baseline:** age/gender eligibility, ordered by due date, generic SMS in Arabic or English, no bundling, same capacity.
  - **Wiqaya:** the full pipeline, with the reviewer step simulated as accepting 90% of flags and rejecting 10% at random. Rejections are logged.
- The response model uses `LatentTruth.response_propensity_by_channel`, plus effects for language match, distance and bundling from `simulation.yaml`. **Models never see these parameters.**
- On attendance, screening detects latent conditions with configured sensitivity/specificity, and the new diagnoses are written back as FHIR resources.
- Outputs go to `data/runs/<run_id>/`: communications, appointments, encounters, detections and a metrics JSON.

**Sensitivity analysis.** `make sensitivity` re-runs with three alternative response-parameter sets (weaker language effect, weaker bundling effect, stronger distance effect) and reports how the Wiqaya-vs-baseline difference changes. This guards against the simulator flattering its own design. Report the results honestly in `docs/EVALUATION.md`.

---

## 7. Evaluation and equity (`wiqaya.evaluate`)

**Metrics per policy**, overall and per segment (nationality group, language, age band, sex, district, housing type, insurance tier):
- reach: % of people with gaps who were contacted;
- **completed screenings/WCVs per 100 contacts** (primary endpoint);
- % of gaps closed within 12 weeks;
- median days from flag to attendance;
- follow-up completion for abnormal results;
- FP rate (high priority, screen normal) and FN rate (latent condition but not prioritised or not reached);
- calibration slope, intercept and Brier score on held-out people, plus a reliability-curve data table;
- yield per 1,000 screened, by condition;
- decline/opt-out rate;
- reviewer override rate;
- flags per available slot.

**Small-cell rule.** `governance.suppress(df, min_n=11)` replaces any cell with denominator < 11 by `"suppressed (n<11)"`. **Every** API response that returns aggregates goes through it. Tests prove it.

**Insufficient-data rule.** A segment with fewer than `min_eval_n` (default 100) held-out people shows "Model not validated for this segment" instead of calibration numbers.

**Reporting.** Produce `docs/EVALUATION.md` automatically:
- tables for each metric;
- a baseline-vs-Wiqaya comparison;
- the sensitivity analysis;
- a TRIPOD+AI-style checklist of what is and isn't covered.

---

## 8. API and web app

### 8.1 API (FastAPI, `/api/v1`)

**Access**
- Auth: `POST /session/guest {role}` returns a signed session cookie. Roles: `coordinator`, `planner`, `family`, `admin`.
- There is no password login in the prototype. The UI shows the login form for realism, but only Guest works.
- Middleware enforces role permissions, writes an `AuditEvent` for every read of person-level data (with `fields_read`), and strips genomic fields for roles other than `admin`/clinician.

**Endpoints**

Coordinator:
- `GET /worklist?clinic_id&pathway&page`
- `GET /people/{id}`: gaps, flag, rule citations, SHAP phrases, household
- `GET /households/{id}`
- `POST /flags/{id}/decision {accepted|changed|rejected, note}`
- `POST /outreach/preview {flag_id}`: rendered message, channel, timing
- `GET /family-graph/{person_id}?depth=2`, filtered by consent

Planner:
- `GET /planner/districts`: gap density, uptake, need vs capacity
- `GET /planner/equity?policy=baseline|wiqaya&segment=...`
- `GET /planner/calibration`
- `GET /planner/compare`

Family:
- `GET /family/{household_id}/messages`
- `POST /family/{person_id}/preferences`

Admin:
- `GET /admin/rules`: list with version, source, status and verification state
- `GET /admin/provenance`
- `GET /admin/audit?limit`
- `GET /admin/model-card`

Meta:
- `GET /meta/demo-personas`
- `GET /healthz`

Generate an OpenAPI client for the web app.

### 8.2 Web app (Next.js)

**Visual language** (matches the submission deck):
- warm neutral background `#F7F4F0`;
- ink `#2E2A26`;
- primary teal `#0E6B68`;
- human-decision/alert coral `#B5543F`;
- borders `#C9BEB1`.

Use one font family (system sans or Inter). The "Simulated cohort" badge is fixed in the header on every page.

**Pages**

1. **Landing / login**
   - Wiqaya wordmark and one-line value proposition.
   - Disabled email/password fields with the note "Prototype: use guest access".
   - **Continue as Guest** button, then a role picker with a one-line description per role.
   - Footer: data provenance link and OSM attribution.
2. **Coordinator worklist**
   - Table: rank, person (masked name + age + sex), pathway, gap status, days overdue, priority band, top reason, slot.
   - Filters by clinic and pathway.
   - Banner: "Population prioritisation, not a clinical decision."
3. **Person / household detail**
   - Gap cards, each showing the rule title, `rule_id@version`, source link, evidence values and status.
   - Priority breakdown (risk / time / no-show) and SHAP phrases.
   - Household members and their gaps, with a "Bundle into one day" suggestion.
   - Family-graph panel (clinician/admin only for genomic detail).
   - Decision buttons (Accept / Change / Reject with reason).
   - Message preview in the chosen language and channel, with an English gloss.
4. **Planner console**
   - District map (Leaflet + OSM tiles + attribution; fallback to an SVG district grid if tiles are blocked) coloured by unmet need per 1,000, with hatching for suppressed cells.
   - Equity table by segment, with baseline vs Wiqaya side by side.
   - Calibration reliability plot.
   - Primary-endpoint KPI cards.
   - Sensitivity-analysis panel.
5. **Family view**
   - Messages as received (rendered phone-style) for the selected demo household.
   - Preference centre: channel order, opt-out per pathway, remind later, decline with reason.
6. **Admin**
   - Rule library with verification status and `machine_draft` translation flags.
   - Provenance register.
   - Model card.
   - Audit log viewer.
   - Config weights (read-only).
7. **About / limitations**
   - Renders `docs/ASSUMPTIONS_AND_LIMITATIONS.md`.

**Accessibility:** keyboard navigable; WCAG AA contrast; `lang` and `dir="rtl"` on Arabic message previews; tables with proper headers.

---

## 9. Governance and documentation (all in `docs/`, all required for submission)

| File | Contents |
|---|---|
| `ARCHITECTURE.md` | Six-layer diagram (Mermaid) matching the deck: Data sources → Ingest & consent → FHIR store → Engines (care-gap, family graph, prioritisation) → Outreach → Consoles, with a governance band. Plus the 8-step workflow loop with the human gate at step 5. |
| `DATA_PROVENANCE.md` | Table: source, type, owner, sensitivity, licence/permission, personal data (Y/N), how used, retrieved_on. Covers the generator (team, synthetic), Synthea if used (Apache-2.0), SCAD aggregates used for calibration, guideline texts (USPSTF/CDC public domain; NICE cited), ClinVar (NCBI), OpenStreetMap (ODbL, attribution), message library (team), LLM API if enabled. States explicitly: **no real personal data, no organiser data, no employer or client data.** |
| `ASSUMPTIONS_AND_LIMITATIONS.md` | Every placeholder assumption from config. Simulator circularity and the sensitivity analysis. Machine-drafted translations. Demo-encoded rules pending clinical validation. No real-world validation. FHIR sample load. Non-diagnostic positioning. |
| `DEPENDENCIES.md` | Runtime and services. |
| `MODEL_CARD.md` | For Model R and Model N: intended use, out-of-scope uses (insurance pricing, eligibility denial, diagnosis), data, features, excluded features, metrics overall and per segment, calibration, known failure modes, update policy. |
| `RISKS_AND_SAFEGUARDS.md` | Privacy, security, bias, explainability, misuse, human oversight and failure modes, each linked to the code that implements the safeguard. |
| `THIRD_PARTY_LICENSES.md` | Generated from `uv pip list` / `pnpm licenses`, plus HAPI FHIR, OSM. |
| `CODES.md` | Code systems used, and every local code. |
| `DECISIONS.md` | Running log of implementation decisions. |
| `EVALUATION.md` | Auto-generated (see §7). |
| `DEMO_SCRIPT.md` | See §11. |
| `SUBMISSION_CHECKLIST.md` | Maps each challenge criterion (1–5) and each judging criterion to the feature, screen and doc that addresses it. |

The root `README.md` covers quick start, architecture summary, guest access and the "Simulated cohort" disclaimer.

---

## 10. Testing and quality gates

- `make test` runs:
  - pytest unit tests: rules golden cases, consent filtering, suppression, fairness floor, determinism, message library checks, API permission tests (family role cannot read genomic fields; planner gets only aggregates);
  - hypothesis property tests: a rule never fires outside its age bounds, and a person with `clinical_data` denied never gets a gap.
- `make e2e` runs a Playwright smoke test: guest login for each role, open the worklist, open demo persona 1, accept a flag, preview a message, open the equity console, and confirm the suppressed-cell hatching renders.
- Linting: ruff + mypy (strict on `rules`, `governance`, `api`); eslint + tsc for the web app.
- CI: GitHub Actions workflow running lint and tests on push.

---

## 11. Demo personas and script

Seed these with fixed IDs (`demo-001`…), so the 3-minute demo is reproducible.

**Al-Hammadi household** (Emirati, Khalifa City, villa, Arabic, WhatsApp; all consents granted)
- **Father, 41** (`demo-001`):
  - LDL persistently high;
  - genomic finding LDLR pathogenic (illustrative);
  - FH confirmed in history 3 weeks before T0.
  - **He is the index case.**
- **Mother, 36** (`demo-002`): cervical screen overdue by 14 months.
- **Son, 9** (`demo-003`) and **daughter, 4** (`demo-004`):
  - `CASCADE_FH` clinician tasks;
  - the daughter's 4-year WCV is also overdue.
- **Father's brother, 45** (`demo-005`): lives in Al Shamkha, different household; a `CASCADE_FH` task; family_links consent granted.

**Musaffah labour accommodation**
- **Worker, 38** (`demo-010`):
  - Indian, Malayalam, basic phone, SMS only;
  - BMI 29, HbA1c 6.1% eighteen months ago;
  - `FOLLOWUP_PREDIABETES` and `ADULT_T2D_SCREEN` overdue;
  - routed to the mobile van slot at his accommodation.

**Consent edge case**
- **Person** (`demo-020`): family_links denied. Show that the graph excludes them and that no cascade task is created.

**`docs/DEMO_SCRIPT.md`** steps, matching the deck:
1. Guest login as Coordinator.
2. The worklist shows the Al-Hammadi household ranked high.
3. Open the father: rule citations, SHAP phrases, family graph.
4. The cascade tasks require clinician sign-off. Accept.
5. Family view: the mother's WhatsApp in Arabic offers one combined visit day.
6. Show the worker's SMS in Malayalam and the van slot.
7. Planner console: completed screenings per 100 contacts, Wiqaya vs baseline; equity table with suppressed cells; calibration.
8. Admin: the rule library with sources, and the provenance register.

---

## 12. Milestones

Each milestone ends with: tests green, docs updated, commit, a short report to the user, then **stop**.

| # | Milestone | Acceptance |
|---|---|---|
| 0 | Plan & scaffold: `PLAN.md`, repo layout, Makefile targets (stubs), docker-compose with HAPI + Postgres up, CI skeleton, `.env.example` | `make up` starts HAPI; `curl localhost:8080/fhir/metadata` returns a CapabilityStatement |
| 1 | Content & config: names, districts, clinics (OSM fetch + fallback), calendar, capacity, all rule YAMLs with verified sources, full message library, blocklist, ClinVar fetch + fallback | `make content-check` passes: all sources verified or flagged, all templates complete and within limits |
| 2 | Generator + loaders: population, history period, latent truth, consents, demo personas; NDJSON → HAPI (sample) and → DuckDB | `make data load` works; population report is sane; determinism test passes; demo personas are retrievable through the HAPI REST API |
| 3 | Care-gap engine + family graph | Golden tests pass; 20k run in under 60 s; demo personas show the expected gaps and cascade tasks; consent edge case behaves correctly |
| 4 | Models + priority + capacity fit + fairness floor | Held-out AUROC and calibration reported; SHAP phrases render; capacity respected; fairness-floor test passes |
| 5 | Outreach orchestrator + simulator + evaluation | `make simulate` produces baseline and Wiqaya runs; `docs/EVALUATION.md` generated; sensitivity analysis done |
| 6 | API with RBAC, audit, suppression; uplift model (stretch) | Permission tests pass; every aggregate endpoint is suppression-checked |
| 7 | Web app, all pages + guest flow | Playwright smoke passes; every metric shows the "Simulated cohort" badge |
| 8 | Docs, demo polish, deploy | All docs in §9 complete; `make demo` works from a clean clone; deployed URL with guest access; `SUBMISSION_CHECKLIST.md` filled |

**Time budget:** submission is 20 Nov 2026. Milestones 0–3 by 13 Nov, 4–6 by 17 Nov, 7–8 by 19 Nov, leaving a buffer day. If behind schedule, cut in this order:
1. uplift model;
2. CQL export;
3. Synthea path;
4. sensitivity panel in the UI (keep it in docs);
5. Leaflet map (keep the SVG grid).

**Never cut:** consent enforcement, suppression, the "Simulated cohort" labels, rule citations, the human-review step, or the docs.

---

## 13. Deployment (Milestone 8)

**Default target: a single Ubuntu VPS**
- Docker Compose with:
  - Caddy as a reverse proxy with automatic HTTPS;
  - HAPI restricted to the internal network only;
  - the API and web app public.
- Seed data is generated at build time with the fixed seed.

**Alternative: Azure Container Apps in a UAE region**
- Same images; document it in `docs/DEPLOYMENT.md` as the pilot path.

**Hardening**
- Rate-limit guest session creation.
- Guest sessions are read-mostly. Decisions and preferences write to a per-session overlay that resets after 2 hours.
- No admin write endpoints.
- Security headers are set.

---

## 14. Definition of done

- A judge opens the URL, clicks **Continue as Guest**, and within 3 minutes can follow `DEMO_SCRIPT.md` end to end without errors.
- Every number on screen is traceable to a run ID and labelled "Simulated cohort".
- Every flag shows its rule citation and version; every model-driven ordering shows its drivers.
- No real personal data anywhere in the repo or the deployment.
- `docs/` contains the full set in §9, and `SUBMISSION_CHECKLIST.md` maps every challenge and judging criterion to evidence.
