"""Pinned demo personas (PROMPT.md §11). Fixed ids, fixed histories, seeded before the random cohort."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from wiqaya.common import config as C
from wiqaya.generator.entities import Cohort, Consent, ContactPreference, FamilyHistory, GenomicFinding
from wiqaya.generator.history import Recorder
from wiqaya.generator.population import PopulationBuilder

D = date.fromisoformat
ALL_CONSENTS = ("clinical_data", "family_links", "genomic", "contact_sms", "contact_whatsapp", "contact_call",
                "chw_visit")  # fmt: skip

PERSONA_IDS = ["demo-001", "demo-002", "demo-003", "demo-004", "demo-005", "demo-006", "demo-007",
               "demo-010", "demo-020"]  # fmt: skip

DESCRIPTIONS: dict[str, str] = {
    "demo-001": "Al-Hammadi father, 41 – FH index case (LDLR finding, FH confirmed 3 weeks before T0)",
    "demo-002": "Al-Hammadi mother, 36 – cervical screening overdue by ~14 months",
    "demo-003": "Al-Hammadi son, 9 – CASCADE_FH clinician task",
    "demo-004": "Al-Hammadi daughter, 4 – CASCADE_FH task and 4-year Well-Child Visit overdue",
    "demo-005": "Father's brother, 45 – lives in Al Shamkha; CASCADE_FH task",
    "demo-010": "Musaffah worker, 38 – Malayalam, basic phone, SMS only; prediabetes follow-up overdue",
    "demo-020": "Father's sister, 38 – family_links consent DENIED: excluded from the graph, no cascade task",
}


def _latent_defaults() -> dict[str, Any]:
    return {
        "fh_carrier": False, "hbb_carrier": False, "brca_carrier": False, "consanguineous_marriage": False,
        "undiagnosed_t2d": False, "prediabetes": False, "hypertension": False, "dyslipidaemia": False,
        "cervical_cin2plus": False, "colorectal_advanced_neoplasia": False, "developmental_delay": False,
        "child_high_bmi": False, "bmi": None,
        "family_history": {"t2d": False, "premature_cvd": False, "colorectal": False, "breast": False},
        "response_propensity_by_channel": {"whatsapp": 0.4, "sms": 0.0, "call_script": 0.3, "chw_script": 0.6},
        "language_sensitivity": 1.0, "distance_sensitivity": 1.0, "bundle_effect": 1.0,
    }  # fmt: skip


def create_people(b: PopulationBuilder) -> None:
    """Create persona households and people (before the random cohort)."""
    t0 = b.t0
    common = {"preferred_language": "ar", "literacy_proxy": "high", "insurance_tier": "Thiqa",
              "has_regular_clinic": True, "pinned": True}  # fmt: skip

    def person(hh: Any, pid: str, given: str, family: str, sex: str, born: str, role: str, **kw: Any) -> Any:
        age = (t0 - D(born)).days / 365.25
        p = b.make_person(hh, sex, age, role, family=family, pid=pid, given=given, **{**common, **kw})
        p.birth_date = D(born)
        p.phone_type = kw.get("phone_type", "smartphone" if age >= 13 else "none")
        return p

    h1 = b.make_household("emirati", "khalifa_city", "villa", hid="hh-demo-001")
    f = person(h1, "demo-001", "Khalid", "Al-Hammadi", "male", "1985-06-14", "head")
    m = person(h1, "demo-002", "Mariam", "Al-Hammadi", "female", "1990-03-02", "spouse")
    s = person(h1, "demo-003", "Saeed", "Al-Hammadi", "male", "2017-04-20", "child")
    d = person(h1, "demo-004", "Shamma", "Al-Hammadi", "female", "2022-07-05", "child")
    b.link(f.id, m.id, "spouse")
    for kid in (s, d):
        b.link(kid.id, m.id, "mother")
        b.link(kid.id, f.id, "father")
    b.link(s.id, d.id, "sibling")

    h2 = b.make_household("emirati", "al_shamkha", "villa", hid="hh-demo-002")
    u = person(h2, "demo-005", "Hamad", "Al-Hammadi", "male", "1981-09-10", "head")
    w = person(h2, "demo-006", "Hessa", "Al-Hammadi", "female", "1984-02-11", "spouse")
    c = person(h2, "demo-007", "Rashid", "Al-Hammadi", "male", "2014-12-03", "child")
    b.link(u.id, w.id, "spouse")
    b.link(c.id, w.id, "mother")
    b.link(c.id, u.id, "father")
    b.link(f.id, u.id, "sibling")

    h3 = b.make_household("emirati", "mbz_city", "villa", hid="hh-demo-003")
    sis = person(h3, "demo-020", "Noura", "Al-Hammadi", "female", "1988-01-22", "head")
    b.link(f.id, sis.id, "sibling")
    b.link(u.id, sis.id, "sibling")

    van = C.van_stops()["van_1_musaffah"]
    h4 = b.make_household("indian", "musaffah", "labour_accommodation", hid="hh-demo-010")
    h4.lat, h4.lon = van["lat"] + 0.002, van["lon"] + 0.002
    h4.primary_language = "ml"
    person(h4, "demo-010", "Biju", "Nair", "male", "1988-05-17", "worker", preferred_language="ml",
           literacy_proxy="low", insurance_tier="Basic", has_regular_clinic=False, phone_type="basic")  # fmt: skip
    for _ in range(6):
        b.make_person(h4, "male", float(b.rng.uniform(24, 50)), "worker", labour=True)


def apply_records(c: Cohort, t0: date) -> None:
    """Fixed latent truth, clinical history, consents and preferences for the personas."""
    rec = Recorder(c, prefix="demo-")
    for pid in PERSONA_IDS:
        c.latent[pid] = _latent_defaults()
    L = c.latent
    L["demo-001"].update(fh_carrier=True, dyslipidaemia=False, dyslipidaemia_diagnosed=True, fh_diagnosed=True,
                         bmi=27.5, genome_programme=True)  # fmt: skip
    L["demo-001"]["family_history"]["premature_cvd"] = True
    L["demo-002"].update(bmi=24.1)
    L["demo-003"].update(fh_carrier=True, dyslipidaemia=True)
    L["demo-004"].update(fh_carrier=False)
    L["demo-005"].update(fh_carrier=True, dyslipidaemia=True, bmi=28.0)
    L["demo-006"].update(bmi=26.0)
    L["demo-020"].update(fh_carrier=True, dyslipidaemia=True, bmi=23.5)
    L["demo-010"].update(prediabetes=True, bmi=29.0)
    L["demo-010"]["response_propensity_by_channel"] = {"whatsapp": -0.5, "sms": -0.6, "call_script": -0.3,
                                                       "chw_script": 0.5}  # fmt: skip

    def visit(pid: str, day: str, typ: str, clinic: str, values: dict[str, float]) -> None:
        e = rec.encounter(pid, D(day), typ, clinic, True, "self")
        for k, v in values.items():
            rec.obs(pid, D(day), k, v, e.id)

    people = {p.id: p for p in c.people}
    cl = {pid: people[pid].assigned_clinic_id for pid in PERSONA_IDS}

    # Father: LDL persistently high; FH confirmed 3 weeks before T0; LDLR finding (illustrative).
    visit(
        "demo-001",
        "2025-01-20",
        "adult_screen",
        cl["demo-001"],
        {"bmi": 27.2, "sbp": 124, "dbp": 80, "hba1c": 5.4, "ldl": 238},
    )
    visit("demo-001", "2025-09-15", "chronic_review", cl["demo-001"], {"bmi": 27.4, "sbp": 122, "dbp": 78, "ldl": 245})
    visit("demo-001", "2026-09-15", "chronic_review", cl["demo-001"], {"bmi": 27.5, "sbp": 121, "dbp": 79, "ldl": 251})
    rec.condition("demo-001", "dyslipidaemia", D("2025-01-20"))
    rec.condition("demo-001", "fh", t0 - timedelta(days=21))
    ldlr = (C.reference("clinvar_cache.json")["genes"].get("LDLR") or [{}])[0]
    c.genomic.append(GenomicFinding("gen-demo-001", "demo-001", "LDLR", ldlr.get("variation_id"),
                                    ldlr.get("name", "illustrative variant"), "pathogenic", D("2026-09-20")))  # fmt: skip
    c.family_history.append(FamilyHistory("fhx-demo-001", "demo-001", "father", "premature_cvd", 52))

    # Mother: last cervical cytology ~50 months before T0 -> ~14 months overdue on a 36-month interval.
    visit("demo-002", "2022-09-01", "adult_screen", cl["demo-002"], {"cytology": 0.0, "bmi": 23.8})
    visit("demo-002", "2026-05-10", "adult_screen", cl["demo-002"], {"bmi": 24.1, "sbp": 112, "dbp": 72})

    # Son: up to date with WCV and vaccines.
    visit("demo-003", "2025-04-24", "wcv", cl["demo-003"], {"bmi_pct": 58})
    visit("demo-003", "2026-04-28", "wcv", cl["demo-003"], {"bmi_pct": 61})
    # Daughter: 3-year WCV done, 4-year WCV (due 2026-07-05) missed.
    visit("demo-004", "2024-01-10", "wcv", cl["demo-004"], {"dev_screen": 0.0, "autism_screen": 0.0, "bmi_pct": 55})
    visit("demo-004", "2024-07-15", "wcv", cl["demo-004"], {"autism_screen": 0.0, "bmi_pct": 52})
    visit("demo-004", "2025-01-08", "wcv", cl["demo-004"], {"dev_screen": 0.0, "bmi_pct": 50})
    visit("demo-004", "2025-07-12", "wcv", cl["demo-004"], {"bmi_pct": 54})
    sched = C.cfg("schedules")["immunisation"]["doses"]
    for kid in ("demo-003", "demo-004", "demo-007"):
        born = people[kid].birth_date
        for dose in sched:
            dd = born + timedelta(days=int(dose["age_months"] * 30.4375) + 7)
            if dd < t0 - timedelta(days=30):
                rec.imm(kid, dose["vaccine"], dd)

    # Brother (Al Shamkha): lipids last checked before the index diagnosis.
    visit(
        "demo-005",
        "2024-12-01",
        "adult_screen",
        cl["demo-005"],
        {"bmi": 28.0, "sbp": 128, "dbp": 79, "hba1c": 5.6, "ldl": 182},
    )
    visit("demo-006", "2026-02-14", "adult_screen", cl["demo-006"], {"bmi": 26.0, "sbp": 118, "dbp": 76, "hba1c": 5.3})
    visit("demo-007", "2026-01-05", "wcv", cl["demo-007"], {"bmi_pct": 64})
    # Sister (family_links denied).
    visit(
        "demo-020",
        "2025-11-10",
        "adult_screen",
        cl["demo-020"],
        {"bmi": 23.5, "sbp": 114, "dbp": 74, "hba1c": 5.2, "ldl": 176, "cytology": 0.0},
    )

    # Worker: BMI 29, HbA1c 6.1% eighteen months before T0, never followed up.
    van_clinic = cl["demo-010"]
    visit("demo-010", "2025-05-01", "mobile_van", van_clinic, {"bmi": 29.0, "hba1c": 6.1, "sbp": 124, "dbp": 78})

    # Consents: everything granted, except the edge case and the worker's channels.
    n = 0
    for pid in PERSONA_IDS:
        p = people[pid]
        for cat in ALL_CONSENTS:
            if cat == "genomic" and pid != "demo-001":
                continue
            if cat == "contact_whatsapp" and p.phone_type != "smartphone":
                continue
            if cat in ("contact_sms", "contact_call") and p.phone_type == "none":
                continue
            status = "granted"
            if pid == "demo-020" and cat == "family_links":
                status = "denied"
            if pid == "demo-010" and cat == "contact_call":
                status = "denied"
            n += 1
            c.consents.append(Consent(f"consent-demo-{n:03d}", pid, cat, status, D("2025-06-01")))
    for pid in PERSONA_IDS:
        p = people[pid]
        if pid == "demo-010":
            order = ["sms", "chw_script"]
        elif p.phone_type == "smartphone":
            order = ["whatsapp", "sms", "call_script", "chw_script"]
        else:
            order = ["chw_script"]
        c.preferences.append(ContactPreference(pid, order))
