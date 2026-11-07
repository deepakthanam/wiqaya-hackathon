"""Data provenance register (PROMPT.md §9, DATA_PROVENANCE.md). Served by GET /admin/provenance."""

from __future__ import annotations

from typing import Any

REGISTER: list[dict[str, Any]] = [
    {"source": "Wiqaya synthetic population generator", "type": "Synthetic person-level records (FHIR R4)",
     "owner": "Wiqaya team", "sensitivity": "None (synthetic)", "licence": "Team-owned", "personal_data": "N",
     "use": "Every person, household, encounter, result, consent and message in the app", "retrieved_on": "generated"},
    {"source": "config/population.yaml placeholder assumptions", "type": "Aggregate parameters",
     "owner": "Wiqaya team", "sensitivity": "None", "licence": "Team-owned", "personal_data": "N",
     "use": "Demographic shares, prevalence, behaviour. To be replaced with SCAD/DOH published aggregates",
     "retrieved_on": "n/a"},
    {"source": "USPSTF recommendation statements", "type": "Guideline text (cited)", "owner": "USPSTF / AHRQ",
     "sensitivity": "Public", "licence": "US Government work – public domain", "personal_data": "N",
     "use": "Adult screening, BP follow-up, child BMI, BRCA rules (demo encodings)", "retrieved_on": "2026-11-07"},
    {"source": "AAP / Bright Futures periodicity schedule; AAP clinical reports (PubMed)", "type": "Guideline (cited)",
     "owner": "American Academy of Pediatrics", "sensitivity": "Public", "licence": "© AAP; cited, not reproduced",
     "personal_data": "N", "use": "WCV, developmental and autism screening schedules", "retrieved_on": "2026-11-07"},
    {"source": "CDC child and adolescent immunization schedule", "type": "Guideline (placeholder schedule)",
     "owner": "US CDC", "sensitivity": "Public", "licence": "US Government work – public domain",
     "personal_data": "N", "use": "Placeholder dose table pending the UAE/Abu Dhabi schedule", "retrieved_on": "2026-11-07"},
    {"source": "DOH Abu Dhabi / ADPHC Circular 2026/77 (immunisation schedule)", "type": "Regulatory circular (cited)",
     "owner": "Department of Health – Abu Dhabi", "sensitivity": "Public", "licence": "Cited, not reproduced",
     "personal_data": "N", "use": "Reference for replacing the placeholder schedule", "retrieved_on": "2026-11-07"},
    {"source": "ADA Standards of Care in Diabetes 2026 (PMC copy)", "type": "Guideline (cited)",
     "owner": "American Diabetes Association", "sensitivity": "Public", "licence": "© ADA; cited, not reproduced",
     "personal_data": "N", "use": "Prediabetes range and yearly retest", "retrieved_on": "2026-11-07"},
    {"source": "NICE CG71 Familial hypercholesterolaemia", "type": "Guideline (cited)", "owner": "NICE",
     "sensitivity": "Public", "licence": "© NICE; cited, not reproduced", "personal_data": "N",
     "use": "FH cascade testing rule", "retrieved_on": "2026-11-07"},
    {"source": "NCBI ClinVar via E-utilities", "type": "Variant reference records", "owner": "NCBI / NLM",
     "sensitivity": "Public", "licence": "Public NCBI data; attribution", "personal_data": "N",
     "use": "Illustrative variant references on synthetic genomic findings", "retrieved_on": "2026-11-07"},
    {"source": "OpenStreetMap (Nominatim, Overpass)", "type": "Geodata", "owner": "OpenStreetMap contributors",
     "sensitivity": "Public", "licence": "ODbL 1.0 – attribution required", "personal_data": "N",
     "use": "District centroids, clinic density (names stripped), map tiles", "retrieved_on": "2026-11-07"},
    {"source": "UAE public holiday announcements (u.ae, MoHRE, national press)", "type": "Calendar dates",
     "owner": "UAE Government", "sensitivity": "Public", "licence": "Public information", "personal_data": "N",
     "use": "No-send days, clinic closures, Ramadan timing", "retrieved_on": "2026-11-07"},
    {"source": "HL7 / LOINC / SNOMED CT / CVX via tx.fhir.org", "type": "Terminology look-ups",
     "owner": "HL7, Regenstrief, SNOMED International, CDC", "sensitivity": "Public",
     "licence": "Per code system terms (LOINC, SNOMED CT affiliate terms apply to production use)", "personal_data": "N",
     "use": "Verified codes in FHIR resources (CODES.md)", "retrieved_on": "2026-11-07"},
    {"source": "Outreach message library", "type": "Message templates", "owner": "Wiqaya team",
     "sensitivity": "None", "licence": "Team-owned", "personal_data": "N",
     "use": "English source; ar/ur/hi/ml/tl machine drafts pending native review", "retrieved_on": "n/a"},
    {"source": "LLM API", "type": "Optional paraphrasing", "owner": "n/a", "sensitivity": "n/a", "licence": "n/a",
     "personal_data": "N", "use": "Disabled by default (LLM_ENABLED=false); no provider bundled", "retrieved_on": "n/a"},
    {"source": "Anthropic Claude API (planner analyst)", "type": "Optional AI agent", "owner": "Anthropic",
     "sensitivity": "Aggregate, suppressed simulated figures only", "licence": "Anthropic commercial terms",
     "personal_data": "N", "use": "Off unless ANTHROPIC_API_KEY is set; answers planner questions from suppressed "
     "aggregates; proposals need human approval (D-045)", "retrieved_on": "n/a"},
]  # fmt: skip

STATEMENT = (
    "No real personal data, no organiser data, and no employer or client data are used anywhere in this prototype. "
    "Every person-level record is synthetic."
)
