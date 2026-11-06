"""Canonical entities -> FHIR R4 resources (PROMPT.md §3.2). Every resource is tagged 'Simulated cohort'."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from datetime import date
from typing import Any

from wiqaya.common import config as C
from wiqaya.generator.entities import Cohort

EXT = "http://wiqaya.health/StructureDefinition/"
ID_PERSON = "http://wiqaya.health/id/person"
GEO = "http://hl7.org/fhir/StructureDefinition/geolocation"
OBS_CAT = "http://terminology.hl7.org/CodeSystem/observation-category"
UCUM = "http://unitsofmeasure.org"

Resource = dict[str, Any]


def local() -> str:
    return str(C.codes()["local_system"])


def tag() -> dict[str, str]:
    return {"system": local(), "code": "synthetic", "display": "Simulated cohort"}


def meta(*extra: dict[str, str]) -> dict[str, Any]:
    return {"tag": [tag(), *extra]}


def coding(spec: dict[str, str]) -> dict[str, str]:
    c = C.codes()
    system = c["local_system"] if spec["system"] == "local" else c["systems"][spec["system"]]
    return {"system": system, "code": str(spec["code"]), "display": spec["display"]}


def cc(specs: list[dict[str, str]], text: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"coding": [coding(s) for s in specs]}
    if text:
        out["text"] = text
    return out


def lcc(code: str, display: str) -> dict[str, Any]:
    return {"coding": [{"system": local(), "code": code, "display": display}]}


def ext(name: str, kind: str, value: Any) -> dict[str, Any]:
    return {"url": EXT + name, kind: value}


def geo(lat: float, lon: float) -> dict[str, Any]:
    return {"url": GEO, "extension": [{"url": "latitude", "valueDecimal": lat},
                                      {"url": "longitude", "valueDecimal": lon}]}  # fmt: skip


def iso(d: date) -> str:
    return d.isoformat()


VITALS = {"bmi", "sbp", "dbp"}
SCREENS = {"dev_screen", "autism_screen"}


def to_resources(c: Cohort) -> Iterator[tuple[str, Resource]]:
    codes = C.codes()
    obs_codes = codes["observations"]
    districts = C.districts()
    clinics = C.clinics()

    for cl in sorted(clinics.values(), key=lambda x: x["id"]):
        yield "Organization", {
            "resourceType": "Organization", "id": cl["id"], "meta": meta(), "active": True,
            "name": cl["name"], "type": [lcc("org-primary-care", "Primary care centre (generic, synthetic)")],
            "address": [{"district": cl["district_id"], "city": districts[cl["district_id"]]["name"],
                         "country": "AE", "extension": [geo(cl["lat"], cl["lon"])]}],
            "extension": [ext("indoor-mall-adjacent", "valueBoolean", bool(cl.get("indoor_mall_adjacent")))],
        }  # fmt: skip
    for s in sorted(C.van_stops().values(), key=lambda x: x["id"]):
        yield "Location", {
            "resourceType": "Location", "id": s["id"], "meta": meta(), "status": "active",
            "name": f"Mobile screening van stop – {s['label']}", "mode": "instance",
            "type": [lcc("loc-mobile-van-stop", "Mobile screening van stop")],
            "position": {"latitude": s["lat"], "longitude": s["lon"]},
            "address": {"district": s["district_id"], "country": "AE"},
            "extension": [ext("van-weekday", "valueString", s["weekday"])],
        }  # fmt: skip

    hh_by_id = {h.id: h for h in c.households}
    members: dict[str, list[str]] = defaultdict(list)
    for p in c.people:
        members[p.household_id].append(p.id)
        yield "Patient", {
            "resourceType": "Patient", "id": p.id, "meta": meta(),
            "identifier": [{"system": ID_PERSON, "value": p.id}],
            "name": [{"family": p.family, "given": [p.given]}],
            "gender": p.sex, "birthDate": iso(p.birth_date),
            "address": [{"district": p.district_id, "city": districts[p.district_id]["name"], "country": "AE",
                         "extension": [geo(p.lat, p.lon)]}],
            "communication": [{"language": {"coding": [{"system": "urn:ietf:bcp:47", "code": p.preferred_language}]},
                               "preferred": True}],
            "generalPractitioner": [{"reference": f"Organization/{p.assigned_clinic_id}"}],
            "extension": [
                ext("nationality-group", "valueString", p.nationality_group),
                ext("literacy-proxy", "valueString", p.literacy_proxy),
                ext("phone-type", "valueString", p.phone_type),
                ext("insurance-tier", "valueString", p.insurance_tier),
                ext("household", "valueString", p.household_id),
                ext("housing-type", "valueString", hh_by_id[p.household_id].housing_type),
                ext("has-regular-clinic", "valueBoolean", p.has_regular_clinic),
                ext("household-role", "valueString", p.role),
            ],
        }  # fmt: skip
    for h in c.households:
        yield "Group", {
            "resourceType": "Group", "id": h.id, "meta": meta(), "type": "person", "actual": True,
            "code": lcc("household", "Household"), "quantity": len(members[h.id]),
            "member": [{"entity": {"reference": f"Patient/{m}"}} for m in members[h.id]],
            "extension": [ext("housing-type", "valueString", h.housing_type),
                          ext("district", "valueString", h.district_id),
                          ext("primary-language", "valueString", h.primary_language),
                          ext("nationality-group", "valueString", h.nationality_group), geo(h.lat, h.lon)],
        }  # fmt: skip

    rel_codes = codes["relationships"]
    rolecode = codes["systems"]["rolecode"]
    for r in c.relationships:
        code = rel_codes.get(r.type, "FAMMEMB")
        yield "RelatedPerson", {
            "resourceType": "RelatedPerson", "id": f"rp-{r.person_id}-{r.related_person_id}", "meta": meta(),
            "active": True, "patient": {"reference": f"Patient/{r.person_id}"},
            "identifier": [{"system": ID_PERSON, "value": r.related_person_id}],
            "relationship": [{"coding": [{"system": rolecode, "code": code},
                                         {"system": local(), "code": f"rel-{r.type}", "display": r.type}]}],
            "extension": [ext("relationship-degree", "valueInteger", r.degree)],
        }  # fmt: skip

    enc_code = codes["encounter_types"]
    for e in c.encounters:
        typ = [lcc(enc_code[e.type], e.type)]
        via = ext("scheduled-via", "valueString", e.scheduled_via)
        if e.attended:
            yield "Encounter", {
                "resourceType": "Encounter", "id": e.id, "meta": meta(), "status": "finished",
                "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
                "type": typ, "subject": {"reference": f"Patient/{e.person_id}"},
                "period": {"start": iso(e.date), "end": iso(e.date)},
                "serviceProvider": {"reference": f"Organization/{e.clinic_id}"}, "extension": [via],
            }  # fmt: skip
        else:
            yield "Appointment", {
                "resourceType": "Appointment", "id": e.id, "meta": meta(), "status": "noshow",
                "serviceType": typ, "start": f"{iso(e.date)}T09:00:00+04:00", "end": f"{iso(e.date)}T09:20:00+04:00",
                "participant": [{"actor": {"reference": f"Patient/{e.person_id}"}, "status": "accepted"}],
                "extension": [via, ext("clinic", "valueString", e.clinic_id)],
            }  # fmt: skip

    attended = {e.id for e in c.encounters if e.attended}
    # Blood pressure: sbp/dbp pairs become one BP panel (LOINC 85354-9) with components.
    bp: dict[tuple[str, date, str | None], dict[str, Any]] = {}
    for o in c.observations:
        if o.key in ("sbp", "dbp"):
            k = (o.person_id, o.date, o.encounter_id)
            bp.setdefault(k, {"id": o.id})[o.key] = o.value
            continue
        spec = obs_codes[o.key]
        cat = "vital-signs" if o.key in VITALS else ("survey" if o.key in SCREENS else "laboratory")
        res: Resource = {
            "resourceType": "Observation", "id": o.id, "meta": meta(), "status": "final",
            "category": [{"coding": [{"system": OBS_CAT, "code": cat}]}],
            "code": cc(spec["codings"]), "subject": {"reference": f"Patient/{o.person_id}"},
            "effectiveDateTime": iso(o.date),
        }  # fmt: skip
        if spec["value_type"] == "coded" or o.key == "mammogram":
            res["valueInteger"] = int(round(o.value))
        else:
            res["valueQuantity"] = {"value": o.value, "unit": spec["unit"], "system": UCUM, "code": spec["unit"]}
        if o.encounter_id in attended:
            res["encounter"] = {"reference": f"Encounter/{o.encounter_id}"}
        yield "Observation", res
    for (pid, d, enc), v in bp.items():
        comps = []
        for key in ("sbp", "dbp"):
            if key in v:
                comps.append({"code": cc(obs_codes[key]["codings"]),
                              "valueQuantity": {"value": v[key], "unit": "mm[Hg]", "system": UCUM, "code": "mm[Hg]"}})  # fmt: skip
        res = {
            "resourceType": "Observation", "id": v["id"], "meta": meta(), "status": "final",
            "category": [{"coding": [{"system": OBS_CAT, "code": "vital-signs"}]}],
            "code": {"coding": [{"system": "http://loinc.org", "code": "85354-9",
                                 "display": "Blood pressure panel with all children optional"}]},
            "subject": {"reference": f"Patient/{pid}"}, "effectiveDateTime": iso(d), "component": comps,
        }  # fmt: skip
        if enc in attended:
            res["encounter"] = {"reference": f"Encounter/{enc}"}
        yield "Observation", res

    cond_codes = codes["conditions"]
    for cnd in c.conditions:
        yield "Condition", {
            "resourceType": "Condition", "id": cnd.id, "meta": meta(),
            "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                                           "code": "active"}]},
            "verificationStatus": {"coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                "code": "confirmed" if cnd.verification == "confirmed" else "provisional"}]},
            "code": cc(cond_codes[cnd.key]["codings"]), "subject": {"reference": f"Patient/{cnd.person_id}"},
            "onsetDateTime": iso(cnd.onset_date), "recordedDate": iso(cnd.onset_date),
        }  # fmt: skip

    vax = codes["vaccines"]
    for im in c.immunizations:
        yield "Immunization", {
            "resourceType": "Immunization", "id": im.id, "meta": meta(), "status": "completed",
            "vaccineCode": cc(vax[im.vaccine]["codings"]), "patient": {"reference": f"Patient/{im.person_id}"},
            "occurrenceDateTime": iso(im.date),
        }  # fmt: skip

    fhx = codes["family_history"]
    fam_role = {"parent": "PRN", "mother": "MTH", "father": "FTH", "sibling": "SIB"}
    for f in c.family_history:
        cond: dict[str, Any] = {"code": {"coding": [coding(fhx[f.condition_key])]}}
        if f.onset_age:
            cond["onsetAge"] = {"value": f.onset_age, "unit": "a", "system": UCUM, "code": "a"}
        yield "FamilyMemberHistory", {
            "resourceType": "FamilyMemberHistory", "id": f.id, "meta": meta(), "status": "completed",
            "patient": {"reference": f"Patient/{f.person_id}"},
            "relationship": {"coding": [{"system": rolecode, "code": fam_role.get(f.relative_type, "FAMMEMB")}]},
            "condition": [cond],
        }  # fmt: skip

    gen = codes["genomic"]
    for g in c.genomic:
        variant = f"ClinVar {g.variant_ref}: {g.variant_name}" if g.variant_ref else "illustrative variant"
        yield "Observation", {
            "resourceType": "Observation", "id": g.id,
            "meta": meta({"system": local(), "code": "genomic", "display": "Genomic finding – restricted"}),
            "status": "final", "category": [{"coding": [{"system": OBS_CAT, "code": "laboratory"}]}],
            "code": {"coding": [coding(gen["panel"])]}, "subject": {"reference": f"Patient/{g.person_id}"},
            "effectiveDateTime": iso(g.date),
            "valueCodeableConcept": lcc(f"variant-{g.classification}", g.classification.replace("_", " ")),
            "component": [
                {"code": {"coding": [coding(gen["gene"])]}, "valueCodeableConcept": {"text": g.gene}},
                {"code": {"coding": [coding(gen["variant"])]}, "valueString": f"{variant} (illustrative only)"},
                {"code": {"coding": [coding(gen["significance"])]}, "valueString": g.classification},
            ],
            "extension": [ext("genomic-source", "valueString", g.source)],
        }  # fmt: skip

    status_map = {"granted": "active", "denied": "rejected", "not_asked": "proposed"}
    for cs in c.consents:
        res = {
            "resourceType": "Consent", "id": cs.id, "meta": meta(), "status": status_map[cs.status],
            "scope": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/consentscope",
                                  "code": "patient-privacy"}]},
            "category": [{"coding": [{"system": "http://loinc.org", "code": "59284-0", "display": "Consent Document"}]},
                         lcc(f"consent-{cs.category}", cs.category)],
            "patient": {"reference": f"Patient/{cs.person_id}"}, "dateTime": f"{iso(cs.date)}T00:00:00+04:00",
            "policy": [{"uri": f"http://wiqaya.health/policy/consent-{cs.category}"}],
        }  # fmt: skip
        if cs.status != "not_asked":
            res["provision"] = {"type": "permit" if cs.status == "granted" else "deny"}
        yield "Consent", res

    for cm in c.communications:
        yield "Communication", {
            "resourceType": "Communication", "id": cm.id, "meta": meta(), "status": "completed",
            "subject": {"reference": f"Patient/{cm.person_id}"}, "sent": f"{iso(cm.sent_at)}T10:00:00+04:00",
            "medium": [lcc(f"channel-{cm.channel}", cm.channel)],
            "payload": [{"contentString": f"template:{cm.template_id} language:{cm.language}"}],
            "extension": [ext("response", "valueString", cm.response), ext("policy", "valueString", cm.policy),
                          ext("pathway", "valueString", cm.pathway), ext("language", "valueString", cm.language),
                          ext("simulated", "valueBoolean", True)],
        }  # fmt: skip


def detected_issue(gap: dict[str, Any], source_url: str, gap_code: str, title: str) -> Resource:
    """A care gap as an R4 DetectedIssue (decision D-006). Population prioritisation, not a diagnosis."""
    severity = "high" if gap["status"] in ("overdue", "followup_overdue", "missed") else "moderate"
    return {
        "resourceType": "DetectedIssue", "id": gap["id"], "meta": meta(), "status": "preliminary",
        "code": lcc(gap_code.replace("local:", ""), title), "severity": severity,
        "patient": {"reference": f"Patient/{gap['person_id']}"},
        "identifiedDateTime": str(gap["created_at"]),
        "detail": f"{gap['rule_id']}@{gap['rule_version']}: {gap['status']} (due {gap['due_date']})",
        "reference": source_url,
        "extension": [
            ext("rule-ref", "valueString", f"{gap['rule_id']}@{gap['rule_version']}"),
            ext("gap-status", "valueString", gap["status"]),
            ext("due-date", "valueDate", str(gap["due_date"])),
            ext("days-overdue", "valueInteger", int(gap["days_overdue"])),
            ext("requires-clinician", "valueBoolean", bool(gap["requires_clinician"])),
            ext("evidence", "valueString", gap["evidence"]),
            ext("fields-read", "valueString", gap["fields_read"]),
        ],
    }  # fmt: skip
