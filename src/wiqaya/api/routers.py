"""API routes (PROMPT.md §8.1). Person-level reads are audited; aggregates are suppressed (n<11)."""

from __future__ import annotations

import json
import math
from typing import Any, Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from wiqaya.api.security import (
    COOKIE,
    GENOMIC_ROLES,
    PERSON_ROLES,
    ROLE_INFO,
    TTL,
    Session,
    audit,
    current_session,
    guest_limiter,
    issue,
    overlays,
    require,
    strip_genomic,
)
from wiqaya.api.store import Store, get_store, hapi_patient
from wiqaya.capacity.slots import sites
from wiqaya.common import config as C
from wiqaya.common.paths import DOCS
from wiqaya.generator.personas import DESCRIPTIONS
from wiqaya.governance.provenance import REGISTER, STATEMENT
from wiqaya.governance.suppress import suppress_records
from wiqaya.graph.family import neighbourhood
from wiqaya.outreach.library import load_library
from wiqaya.outreach.orchestrator import preview

LABEL = "Simulated cohort"
DISCLAIMER = "Population prioritisation, not a clinical decision."
router = APIRouter(prefix="/api/v1")


def envelope(store: Store, data: Any, **extra: Any) -> dict[str, Any]:
    return {"label": LABEL, "run_id": store.run_id, "as_of": store.as_of.isoformat(), **extra, "data": data}


def clean(v: Any) -> Any:
    if v is pd.NaT:  # NaT has isoformat() and would otherwise leak to the UI as the text "NaT"
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [clean(x) for x in v]
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if pd.isna(v) if not isinstance(v, (list, dict, str)) else False:
        return None
    return v


def masked(store: Store, pid: str) -> str:
    p = store.p.loc[pid]
    return f"{p.given[0]}. {p.family[:3]}***"


def site_name(site_id: Any) -> str | None:
    if not isinstance(site_id, str) or not site_id:
        return None
    c = C.clinics().get(site_id)
    if c:
        return str(c["name"])
    v = C.van_stops().get(site_id)
    return f"Mobile Screening Van – {v['label']}" if v else site_id


def decision_of(s: Session, flag_id: str, base: str) -> dict[str, Any]:
    return overlays.get(s.sid).decisions.get(flag_id, {"decision": base, "note": "", "by": None})


# ------------------------------------------------------------------------------------------------- session
class GuestRequest(BaseModel):
    role: Literal["coordinator", "clinician", "planner", "family", "admin"]
    household_id: str = "hh-demo-001"


@router.post("/session/guest", tags=["session"])
def guest(body: GuestRequest, request: Request, response: Response) -> dict[str, Any]:
    """Continue as Guest: signed session cookie for the chosen role. No credentials exist."""
    guest_limiter.check(request.client.host if request.client else "unknown")
    existing = request.cookies.get(COOKIE)
    sid = None
    if existing:
        try:
            sid = current_session(request).sid  # keep the same overlay when switching roles
        except HTTPException:
            sid = None
    token = issue(body.role, sid, body.household_id)
    response.set_cookie(COOKIE, token, max_age=TTL, httponly=True, samesite="lax")
    return {"label": LABEL, "role": body.role, "role_description": ROLE_INFO[body.role], "token": token,
            "expires_in_seconds": TTL}  # fmt: skip


@router.get("/session", tags=["session"])
def whoami(s: Session = Depends(current_session)) -> dict[str, Any]:  # noqa: B008
    return {"role": s.role, "household_id": s.household_id, "roles": ROLE_INFO}


# ------------------------------------------------------------------------------------------------- coordinator
@router.get("/worklist", tags=["coordinator"])
def worklist(clinic_id: str | None = None, pathway: str | None = None, band: str | None = None, page: int = 1,
             page_size: int = 50, s: Session = Depends(require(*PERSON_ROLES))) -> dict[str, Any]:  # noqa: B008  # fmt: skip
    st = get_store()
    f = st.flags
    if clinic_id:
        f = f[(f.site_id == clinic_id) | (f.person_id.map(st.p.assigned_clinic_id) == clinic_id)]
    if pathway:
        f = f[f.top_pathway == pathway]
    if band:
        f = f[f.band == band]
    total = len(f)
    page_size = max(1, min(page_size, 200))
    f = f.sort_values("rank").iloc[(page - 1) * page_size : page * page_size]
    rows = []
    for r in f.itertuples(index=False):
        rule = st.rules[r.top_rule_id]
        rows.append({
            "rank": int(r.rank), "flag_id": r.flag_id, "person_id": r.person_id, "person": masked(st, r.person_id),
            "age": st.age(r.person_id), "sex": st.p.at[r.person_id, "sex"], "household_id": r.household_id,
            "pathway": r.top_pathway, "gap_status": r.top_status, "days_overdue": int(r.max_days_overdue),
            "n_gaps": int(r.n_gaps), "priority": float(r.priority), "priority_band": r.band,
            "top_reason": f"{rule.title} ({rule.ref})", "requires_clinician": bool(r.requires_clinician),
            "slot": {"site": site_name(r.site_id), "date": clean(r.date), "time": clean(r.time)} if isinstance(r.site_id, str)
            else None, "slot_status": r.slot_status,
            "decision": decision_of(s, r.flag_id, r.reviewer_decision)["decision"],
            "fairness_adjusted": bool(r.fairness_adjusted),
        })  # fmt: skip
    audit.write(
        s.role, s.sid, "read", "worklist", clinic_id or "all", ["given", "family", "birth_date", "sex", "care_gaps"]
    )
    clinics = sorted(({"id": c["id"], "name": c["name"]} for c in C.clinics().values()), key=lambda c: c["name"])
    return envelope(st, clean(rows), total=total, page=page, page_size=page_size, disclaimer=DISCLAIMER,
                    clinics=clinics, pathways=sorted(st.flags.top_pathway.unique().tolist()))  # fmt: skip


def gap_cards(st: Store, pid: str) -> list[dict[str, Any]]:
    out = []
    for g in st.gaps_for(pid).sort_values("days_overdue", ascending=False).itertuples(index=False):
        rule = st.rules[g.rule_id]
        out.append({
            "gap_id": g.id, "rule_id": g.rule_id, "rule_ref": g.rule_ref, "title": rule.title, "pathway": g.pathway,
            "status": g.status, "due_date": clean(g.due_date), "days_overdue": int(g.days_overdue),
            "evidence": json.loads(g.evidence), "fields_read": json.loads(g.fields_read),
            "requires_clinician": bool(g.requires_clinician), "rule_status": rule.status,
            "source": {"name": rule.source.name, "year": rule.source.year, "url": rule.source.url,
                       "retrieved_on": rule.source.retrieved_on, "verified": rule.source.verified,
                       "verification_url": rule.source.verification_url},
            "assumptions": list(rule.assumptions),
        })  # fmt: skip
    return out


@router.get("/people/{pid}", tags=["coordinator"])
def person(pid: str, s: Session = Depends(require(*PERSON_ROLES))) -> dict[str, Any]:  # noqa: B008
    st = get_store()
    if pid not in st.p.index:
        raise HTTPException(404, "person not found")
    fhir, source = hapi_patient(pid)
    p = st.p.loc[pid]
    flag = st.flag_by_person.loc[pid].to_dict() if pid in st.flag_by_person.index else None
    fields = ["given", "family", "birth_date", "sex", "nationality_group", "preferred_language", "household_id",
              "care_gaps", "flags", "observations:latest"]  # fmt: skip
    detail: dict[str, Any] = {
        "person_id": pid, "name": f"{p.given} {p.family}", "age": st.age(pid), "sex": p.sex,
        "birth_date": clean(p.birth_date), "district_id": p.district_id, "preferred_language": p.preferred_language,
        "nationality_group": p.nationality_group, "phone_type": p.phone_type, "household_id": p.household_id,
        "housing_type": p.housing_type, "assigned_clinic": site_name(p.assigned_clinic_id),
        "data_source": source, "fhir_banner": None if source == "hapi" else
        "FHIR server not used for this record – showing the DuckDB read model.",
        "fhir": {"resource": f"Patient/{fhir['id']}", "versionId": fhir.get("meta", {}).get("versionId"),
                 "lastUpdated": fhir.get("meta", {}).get("lastUpdated")} if fhir else None,
        "gaps": gap_cards(st, pid),
        "consents": {c: st.cmap.get((pid, c), "not_asked") for c in ("clinical_data", "family_links", "genomic",
                     "contact_sms", "contact_whatsapp", "contact_call", "chw_visit")},
    }  # fmt: skip
    obs = st.observations[st.observations.person_id == pid].sort_values("date")
    detail["latest_results"] = {k: {"value": float(g.value.iloc[-1]), "date": clean(g.date.iloc[-1]), "n": len(g)}
                                for k, g in obs.groupby("key")}  # fmt: skip
    detail["conditions"] = [{"key": c.key, "onset": clean(c.onset_date), "verification": c.verification}
                            for c in st.conditions[st.conditions.person_id == pid].itertuples(index=False)]  # fmt: skip
    if flag:
        shap = json.loads(flag["shap_top3"])
        if s.role not in GENOMIC_ROLES:
            shap = [x for x in shap if x["feature"] != "genomic_flag"]
        w = C.cfg("simulation")["priority"]["weights"]
        detail["flag"] = clean({
            "flag_id": flag["flag_id"], "rank": int(flag["rank"]), "band": flag["band"], "priority": flag["priority"],
            "components": {"risk": flag["risk_percentile"], "time_sensitivity": flag["time_sensitivity"],
                           "no_show": flag["no_show_risk"], "household_bundle": flag["household_bundle_bonus"]},
            "weights": w, "risk_calibrated": flag["risk_calibrated"], "risk_note": flag["risk_note"],
            "shap_top3": shap, "requires_clinician": bool(flag["requires_clinician"]),
            "decision": decision_of(s, flag["flag_id"], flag["reviewer_decision"]),
            "slot": {"site_id": flag.get("site_id"), "site": site_name(flag.get("site_id")), "date": flag.get("date"),
                     "time": flag.get("time"), "status": flag["slot_status"]},
            "contact": {"recipient_id": flag["recipient_id"], "audience": flag["audience"],
                        "channels": json.loads(flag["channels"]), "language": flag["language_plan"],
                        "reason": flag["contact_reason"]},
            "fairness_adjusted": bool(flag["fairness_adjusted"]),
        })  # fmt: skip
    # Index-case information: cascade tasks this person's record created for relatives.
    casc = st.gaps[st.gaps.rule_id.str.startswith("CASCADE")]
    created = [g for g in casc.itertuples(index=False) if pid in json.loads(g.evidence).get("index_person_ids", [])]
    detail["cascade_index"] = {"tasks_created": len(created),
                               "relatives": [g.person_id for g in created]} if created else None  # fmt: skip
    if s.role in GENOMIC_ROLES:
        gen = st.genomic[st.genomic.person_id == pid]
        detail["genomic"] = [{"gene": r.gene, "variant": r.variant, "classification": r.classification,
                              "date": clean(r.date), "consent": st.cmap.get((pid, "genomic"), "not_asked"),
                              "note": "Illustrative ClinVar reference on a synthetic finding"} for r in gen.itertuples()]  # fmt: skip
        fields.append("genomic")
    else:
        detail["genomic"] = "restricted (clinician/admin only)"
    audit.write(s.role, s.sid, "read", "Patient", pid, fields)
    return envelope(st, strip_genomic(clean(detail), s.role), disclaimer=DISCLAIMER)


@router.get("/households/{hid}", tags=["coordinator"])
def household(hid: str, s: Session = Depends(require(*PERSON_ROLES))) -> dict[str, Any]:  # noqa: B008
    st = get_store()
    members = st.household_members(hid)
    if members.empty:
        raise HTTPException(404, "household not found")
    rows = []
    for m in members.itertuples(index=False):
        fl = st.flag_by_person.loc[m.id].to_dict() if m.id in st.flag_by_person.index else None
        rows.append({"person_id": m.id, "name": f"{m.given} {m.family}", "age": st.age(m.id), "sex": m.sex,
                     "role": m.role, "gaps": [{"rule_ref": g["rule_ref"], "title": g["title"], "status": g["status"],
                                               "days_overdue": g["days_overdue"]} for g in gap_cards(st, m.id)],
                     "flag_id": fl["flag_id"] if fl else None, "rank": int(fl["rank"]) if fl else None,
                     "slot": {"site": site_name(fl.get("site_id")), "date": clean(fl.get("date")),
                              "time": clean(fl.get("time"))} if fl else None})  # fmt: skip
    # Only members with a real site and date can share a visit day (unscheduled members have no slot).
    slots = [(r["slot"]["site"], r["slot"]["date"]) for r in rows
             if r["slot"] and r["slot"]["site"] and r["slot"]["date"]]  # fmt: skip
    bundle = None
    if len(slots) > 1 and slots.count(common := max(set(slots), key=slots.count)) > 1:
        bundle = {"site": common[0], "date": common[1], "members": sum(1 for x in slots if x == common),
                  "suggestion": f"Bundle into one day: {sum(1 for x in slots if x == common)} members at {common[0]} "
                                f"on {common[1]}"}  # fmt: skip
    h = st.households[st.households.id == hid].iloc[0]
    audit.write(s.role, s.sid, "read", "Group", hid, ["household members", "care_gaps"])
    return envelope(st, clean({"household_id": hid, "district_id": h.district_id, "housing_type": h.housing_type,
                               "primary_language": h.primary_language, "members": rows, "bundle": bundle}))  # fmt: skip


class Decision(BaseModel):
    decision: Literal["accepted", "changed", "rejected"]
    note: str = Field("", max_length=500)


@router.post("/flags/{flag_id}/decision", tags=["coordinator"])
def decide(flag_id: str, body: Decision, s: Session = Depends(require(*PERSON_ROLES))) -> dict[str, Any]:  # noqa: B008
    st = get_store()
    if flag_id not in st.flag_by_id.index:
        raise HTTPException(404, "flag not found")
    f = st.flag_by_id.loc[flag_id]
    if bool(f.requires_clinician) and body.decision == "accepted" and s.role not in ("clinician", "admin"):
        raise HTTPException(403, "Cascade tasks require clinician sign-off. Switch to the Clinician role to approve.")
    if body.decision in ("rejected", "changed") and not body.note.strip():
        raise HTTPException(422, "A reason is required when rejecting or changing a flag.")
    rec = {"decision": body.decision, "note": body.note, "by": s.role, "flag_id": flag_id,
           "cascade_signed_off": bool(f.requires_clinician) and body.decision == "accepted"}  # fmt: skip
    overlays.get(s.sid).decisions[flag_id] = rec
    audit.write(s.role, s.sid, f"decision:{body.decision}", "DetectedIssue", flag_id, ["flag"])
    return {"label": LABEL, "saved": rec, "note": "Saved to this guest session only (resets after 2 hours)."}


class PreviewRequest(BaseModel):
    flag_id: str
    channel: Literal["whatsapp", "sms", "call_script", "chw_script"] | None = None
    language: Literal["en", "ar", "ur", "hi", "ml", "tl"] | None = None


def _preview(
    st: Store, s: Session, flag_id: str, channel: str | None = None, language: str | None = None
) -> dict[str, Any]:
    f = st.flag_by_id.loc[flag_id].to_dict()
    out = preview(f, st.people, st.gaps, st.flags, channel, language)
    dec = decision_of(s, flag_id, f["reviewer_decision"])
    if out["clinician_approval_required"]:
        if dec.get("cascade_signed_off"):
            index_ok = all(st.granted(i, "family_links") for g in st.gaps_for(f["person_id"]).itertuples()
                           for i in json.loads(g.evidence).get("index_person_ids", []))  # fmt: skip
            out["status"] = "approved: ready to send" if index_ok else "approved: waiting for index consent to share"
    elif dec["decision"] == "rejected":
        out["status"] = "rejected by reviewer: not sent"
    return out


@router.post("/outreach/preview", tags=["coordinator"])
def outreach_preview(body: PreviewRequest, s: Session = Depends(require(*PERSON_ROLES))) -> dict[str, Any]:  # noqa: B008
    st = get_store()
    if body.flag_id not in st.flag_by_id.index:
        raise HTTPException(404, "flag not found")
    audit.write(s.role, s.sid, "preview", "Communication", body.flag_id, ["given", "preferred_language", "slot"])
    return envelope(st, clean(_preview(st, s, body.flag_id, body.channel, body.language)))


@router.get("/family-graph/{pid}", tags=["coordinator"])
def family_graph(pid: str, depth: int = 2, s: Session = Depends(require(*PERSON_ROLES))) -> dict[str, Any]:  # noqa: B008
    st = get_store()
    if pid not in st.p.index:
        raise HTTPException(404, "person not found")
    nb = neighbourhood(st.graph, pid, min(depth, 3))
    casc = st.gaps[st.gaps.rule_id.str.startswith("CASCADE")]
    index_of = {i for g in casc.itertuples(index=False) for i in json.loads(g.evidence).get("index_person_ids", [])}
    nodes = []
    for n in nb["nodes"]:
        node = {"id": n, "label": masked(st, n), "age": st.age(n), "sex": st.p.at[n, "sex"],
                "same_household": st.p.at[n, "household_id"] == st.p.at[pid, "household_id"],
                "has_open_gaps": bool((st.gaps.person_id == n).any()),
                "cascade_task": bool(((casc.person_id == n)).any())}  # fmt: skip
        if s.role in GENOMIC_ROLES:
            node["is_index"] = n in index_of
        nodes.append(node)
    excluded = [{"relationship": r.type, "reason": "family_links consent not granted by both people"}
                for r in st.relationships[st.relationships.person_id == pid].itertuples(index=False)
                if not (st.granted(pid, "family_links") and st.granted(r.related_person_id, "family_links"))]  # fmt: skip
    audit.write(s.role, s.sid, "read", "RelatedPerson", pid, ["relationships", "family_links consent"])
    return envelope(st, {"center": pid, "in_graph": nb["in_graph"], "nodes": nodes, "edges": nb["edges"],
                         "excluded_links": excluded,
                         "consent_note": "Only links where both people granted family_links consent are shown."})  # fmt: skip


# ------------------------------------------------------------------------------------------------- planner
POPULATIONS = {
    "all": "Everyone",
    "labour_accommodation": "Residents of labour accommodation",
    "children_under_6": "Children under 6",
    "adults_65_plus": "Adults 65 and over",
}


def _population(st: Store, population: str) -> pd.DataFrame:
    p = st.people
    if population == "labour_accommodation":
        return p[p.housing_type == "labour_accommodation"]
    age = p.birth_date.map(lambda b: (st.as_of - b).days / 365.25)
    if population == "children_under_6":
        return p[age < 6]
    if population == "adults_65_plus":
        return p[age >= 65]
    return p


def _need_by_district(st: Store, population: str = "all") -> list[dict[str, Any]]:
    d = C.districts()
    pop = _population(st, population)
    ppl = pop.groupby("district_id").size()
    gaps = st.gaps.merge(pop[["id", "district_id"]], left_on="person_id", right_on="id")
    g = gaps.groupby("district_id")
    assigned = st.flags[st.flags.slot_status == "assigned"].merge(pop[["id", "district_id"]], left_on="person_id",
                                                                  right_on="id").groupby("district_id").size()  # fmt: skip
    people_with_gaps = g.person_id.nunique()
    cap = st.buckets.copy()
    cap["district_id"] = cap.site_id.map(lambda x: sites()[x].district_id)
    cap_d = cap.groupby("district_id").capacity.sum()
    seg = {r["segment"]: r for r in st.simulation.get("segments", {}).get("wiqaya", {}).get("district", [])}
    rows = []
    for did, info in sorted(d.items()):
        n = int(ppl.get(did, 0))
        open_gaps = int(g.size().get(did, 0))
        unmet_people = int(people_with_gaps.get(did, 0)) - int(assigned.get(did, 0))
        rows.append({"district_id": did, "name": info["name"], "region": info["region"], "lat": info["lat"],
                     "lon": info["lon"], "n": n, "open_gaps": open_gaps,
                     "gaps_per_1000": round(1000 * open_gaps / n, 1) if n else None,
                     "unmet_need_per_1000": round(1000 * max(unmet_people, 0) / n, 1) if n else None,
                     "slots_12w": int(cap_d.get(did, 0)),
                     "need_vs_capacity": round(int(people_with_gaps.get(did, 0)) / int(cap_d.get(did, 1)), 2)
                     if cap_d.get(did, 0) else None,
                     "wiqaya_completed_per_100_contacts": seg.get(did, {}).get("completed_per_100_contacts")})  # fmt: skip
    return rows


@router.get("/planner/districts", tags=["planner"])
def planner_districts(
    population: Literal["all", "labour_accommodation", "children_under_6", "adults_65_plus"] = "all",
    s: Session = Depends(require("planner", "admin")),  # noqa: B008
) -> dict[str, Any]:
    st = get_store()
    rows = suppress_records(_need_by_district(st, population), min_n=C.cfg("segments")["min_cell_n"])
    return envelope(st, rows, population=population, populations=POPULATIONS)


@router.get("/planner/equity", tags=["planner"])
def planner_equity(policy: Literal["baseline", "wiqaya", "both"] = "both", segment: str = "nationality_group",
                   s: Session = Depends(require("planner", "admin"))) -> dict[str, Any]:  # noqa: B008  # fmt: skip
    st = get_store()
    seg = st.simulation.get("segments", {})
    if segment not in seg.get("wiqaya", {}):
        raise HTTPException(422, f"segment must be one of {sorted(seg.get('wiqaya', {}))}")
    min_n = C.cfg("segments")["min_cell_n"]
    if policy == "both":
        b = {r["segment"]: r for r in seg["baseline"][segment]}
        rows = []
        for r in seg["wiqaya"][segment]:
            br = b.get(r["segment"], {})
            rows.append({"segment": r["segment"], "n": r["n"],
                         "baseline_reach_pct": br.get("reach_pct"), "wiqaya_reach_pct": r["reach_pct"],
                         "baseline_completed_per_100": br.get("completed_per_100_contacts"),
                         "wiqaya_completed_per_100": r["completed_per_100_contacts"],
                         "baseline_gaps_closed_pct": br.get("gaps_closed_pct"), "wiqaya_gaps_closed_pct": r["gaps_closed_pct"]})  # fmt: skip
        data = suppress_records(rows, min_n=min_n)
    else:
        data = suppress_records(seg[policy][segment], min_n=min_n)
    return envelope(st, data, segment=segment, segments=sorted(seg.get("wiqaya", {})))


@router.get("/planner/calibration", tags=["planner"])
def planner_calibration(s: Session = Depends(require("planner", "admin"))) -> dict[str, Any]:  # noqa: B008
    st = get_store()
    out = {}
    for name in ("model_r", "model_n"):
        m = st.models.get(name, {})
        rel = [{**r, "suppressed": False} for r in m.get("test_calibrated", {}).get("reliability", [])]
        segs = {}
        for seg, vals in m.get("segments", {}).items():
            segs[seg] = suppress_records(
                [{"segment": k, **v} for k, v in vals.items()], min_n=C.cfg("segments")["min_cell_n"]
            )
        out[name] = {"label": m.get("label"), "test": {k: v for k, v in m.get("test_calibrated", {}).items()
                                                       if k != "reliability"},
                     "uncalibrated": m.get("test_uncalibrated"), "reliability": suppress_records(rel),
                     "segments": segs, "min_eval_n": C.cfg("segments")["min_eval_n"]}  # fmt: skip
    return envelope(st, clean(out))


@router.get("/planner/compare", tags=["planner"])
def planner_compare(s: Session = Depends(require("planner", "admin"))) -> dict[str, Any]:  # noqa: B008
    st = get_store()
    sim = st.simulation
    return envelope(st, clean({"primary_endpoint": sim.get("primary_endpoint"), "policies": sim.get("policies"),
                               "sensitivity": sim.get("sensitivity"), "capacity_slots": sim.get("capacity_slots"),
                               "weeks": sim.get("weeks")}))  # fmt: skip


# ------------------------------------------------------------------------------------------------- family
def _family_access(s: Session, hid: str) -> None:
    if s.role == "admin":
        return
    if s.role != "family" or hid != s.household_id:
        raise HTTPException(403, "Family view is limited to your own household.")


@router.get("/family/{hid}/messages", tags=["family"])
def family_messages(hid: str, s: Session = Depends(require("family", "admin"))) -> dict[str, Any]:  # noqa: B008
    _family_access(s, hid)
    st = get_store()
    members = st.household_members(hid)
    msgs, seen = [], set()
    prefs = overlays.get(s.sid).preferences
    for m in members.itertuples(index=False):
        if m.id not in st.flag_by_person.index:
            continue
        f = st.flag_by_person.loc[m.id]
        opted = set(prefs.get(f.recipient_id, {}).get("opt_out_pathways", []))
        if f.message_pathway in opted:
            continue
        pv = _preview(st, s, f.flag_id)
        key = (pv["recipient_id"], pv["text"])
        if key in seen:
            continue
        seen.add(key)
        if pv["clinician_approval_required"] and not pv["status"].startswith("approved"):
            continue  # cascade messages appear only after clinician sign-off; they never name a relative
        msgs.append({"to": st.p.at[pv["recipient_id"], "given"], "recipient_id": pv["recipient_id"], **{
            k: pv[k] for k in ("channel", "language", "rtl", "text", "english_gloss", "send_at", "review_status",
                               "pathway", "household_bundled", "slot", "template_id")}})  # fmt: skip
    audit.write(s.role, s.sid, "read", "Communication", hid, ["household messages"])
    return envelope(
        st,
        clean(msgs),
        household_id=hid,
        members=[{"person_id": m.id, "given": m.given} for m in members.itertuples(index=False)],
    )


class Preferences(BaseModel):
    channel_order: list[Literal["whatsapp", "sms", "call_script", "chw_script"]] | None = None
    opt_out_pathways: list[str] = []
    remind_later_until: str | None = None
    decline_reason: str | None = Field(None, max_length=300)


@router.get("/family/{hid}/preferences", tags=["family"])
def get_preferences(hid: str, s: Session = Depends(require("family", "admin"))) -> dict[str, Any]:  # noqa: B008
    _family_access(s, hid)
    st = get_store()
    prefs = overlays.get(s.sid).preferences
    out = {m.id: prefs.get(m.id, {"channel_order": None, "opt_out_pathways": [], "remind_later_until": None})
           for m in st.household_members(hid).itertuples(index=False)}  # fmt: skip
    lib = load_library()
    pathways = [p for p, v in lib.matrix["pathways"].items() if v["kind"] == "outreach"]
    return envelope(st, out, pathways=pathways)


@router.post("/family/{pid}/preferences", tags=["family"])
def set_preferences(pid: str, body: Preferences, s: Session = Depends(require("family", "admin"))) -> dict[str, Any]:  # noqa: B008
    st = get_store()
    if pid not in st.p.index:
        raise HTTPException(404, "person not found")
    _family_access(s, st.p.at[pid, "household_id"])
    overlays.get(s.sid).preferences[pid] = body.model_dump()
    lang = st.p.at[pid, "preferred_language"]
    lang = lang if lang in load_library().languages() else "en"
    from datetime import datetime, time

    from wiqaya.outreach.render import label, render

    if body.opt_out_pathways:
        conf = render(pathway="optout_confirm", audience="adult", channel="whatsapp", language=lang,
                      values={"recipient_first_name": st.p.at[pid, "given"],
                              "pathway_label": label(lang, "pathway_labels", body.opt_out_pathways[0])},
                      send_from=datetime.combine(st.as_of, time(10)))  # fmt: skip
    elif body.remind_later_until:
        conf = render(pathway="remind_later_confirm", audience="adult", channel="whatsapp", language=lang,
                      values={"recipient_first_name": st.p.at[pid, "given"], "until_date": body.remind_later_until},
                      send_from=datetime.combine(st.as_of, time(10)))  # fmt: skip
    else:
        conf = render(pathway="preference_confirm", audience="adult", channel="whatsapp", language=lang,
                      values={"recipient_first_name": st.p.at[pid, "given"]},
                      send_from=datetime.combine(st.as_of, time(10)))  # fmt: skip
    audit.write(s.role, s.sid, "update", "ContactPreference", pid, ["preferences"])
    return {
        "label": LABEL,
        "saved": body.model_dump(),
        "confirmation": conf.as_dict(),
        "note": "Saved to this guest session only. A decline stops further outreach for that pathway.",
    }


# ------------------------------------------------------------------------------------------------- admin
@router.get("/admin/rules", tags=["admin"])
def admin_rules(s: Session = Depends(require("admin", "clinician", "coordinator"))) -> dict[str, Any]:  # noqa: B008
    st = get_store()
    lib = load_library()
    trans: dict[str, dict[str, int]] = {}
    for t in lib.templates.values():
        trans.setdefault(t.language, {}).setdefault(t.review_status, 0)
        trans[t.language][t.review_status] += 1
    rules = [{"id": r.id, "version": r.version, "ref": r.ref, "title": r.title, "pathway": r.pathway, "kind": r.kind,
              "status": r.status, "requires_clinician": r.requires_clinician, "message_pathway": r.message_pathway,
              "source": r.source.model_dump(), "data_required": list(r.data_required), "assumptions": list(r.assumptions),
              "verification_state": "verified" if r.source.verified else "unverified_source",
              "open_gaps": int((st.gaps.rule_id == r.id).sum())} for r in st.rules.values()]  # fmt: skip
    return envelope(
        st,
        rules,
        translations=trans,
        translation_note="Non-English templates are machine drafts and need native-speaker review.",
    )


@router.get("/admin/provenance", tags=["admin"])
def admin_provenance(s: Session = Depends(require("admin", "planner"))) -> dict[str, Any]:  # noqa: B008
    return envelope(get_store(), REGISTER, statement=STATEMENT)


@router.get("/admin/audit", tags=["admin"])
def admin_audit(limit: int = 100, s: Session = Depends(require("admin"))) -> dict[str, Any]:  # noqa: B008
    return envelope(get_store(), audit.recent(min(limit, 1000)))


@router.get("/admin/model-card", tags=["admin"])
def admin_model_card(s: Session = Depends(require("admin", "planner", "clinician"))) -> dict[str, Any]:  # noqa: B008
    st = get_store()
    m = st.models
    card = (DOCS / "MODEL_CARD.md").read_text(encoding="utf-8") if (DOCS / "MODEL_CARD.md").exists() else ""
    return envelope(st, clean({
        "markdown": card, "features_r": m.get("features_r"), "excluded_from_model_r": m.get("excluded_from_model_r"),
        "model_r": {k: v for k, v in m.get("model_r", {}).items() if k not in ("segments",)},
        "model_n": {k: v for k, v in m.get("model_n", {}).items() if k not in ("segments",)},
        "fit": {k: v for k, v in m.get("fit", {}).items() if k != "detail"},
        "fairness": {"adjustments": m.get("fairness", {}).get("adjustments"),
                     "log_sample": st.fairness_log.head(20).to_dict("records")},
    }))  # fmt: skip


@router.get("/admin/config", tags=["admin"])
def admin_config(s: Session = Depends(require("admin"))) -> dict[str, Any]:  # noqa: B008
    sim = C.cfg("simulation")
    return envelope(get_store(), {"priority": sim["priority"], "fairness": C.cfg("segments")["fairness"],
                                  "capacity": C.cfg("capacity"), "policies": sim["policies"],
                                  "note": "Read-only in the prototype. No admin write endpoints exist."})  # fmt: skip


# ------------------------------------------------------------------------------------------------- meta
@router.get("/meta/demo-personas", tags=["meta"])
def demo_personas() -> dict[str, Any]:
    st = get_store()
    rows = []
    for pid, desc in DESCRIPTIONS.items():
        fl = st.flag_by_person.loc[pid] if pid in st.flag_by_person.index else None
        rows.append({"person_id": pid, "description": desc, "household_id": st.p.at[pid, "household_id"],
                     "rank": int(fl["rank"]) if fl is not None else None,
                     "flag_id": fl["flag_id"] if fl is not None else None})  # fmt: skip
    return envelope(st, rows)


@router.get("/meta/limitations", tags=["meta"])
def limitations() -> dict[str, Any]:
    p = DOCS / "ASSUMPTIONS_AND_LIMITATIONS.md"
    return {"label": LABEL, "markdown": p.read_text(encoding="utf-8") if p.exists() else ""}


@router.get("/healthz", tags=["meta"])
def healthz() -> dict[str, str]:
    from wiqaya import __version__

    return {"status": "ok", "version": __version__, "data": "simulated cohort"}


AGGREGATE_PATHS = ["/api/v1/planner/districts", "/api/v1/planner/equity", "/api/v1/planner/calibration",
                   "/api/v1/planner/compare"]  # fmt: skip
