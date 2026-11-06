"""Outreach orchestrator: turn a flag + its slot into a concrete, rendered message (PROMPT.md §6.5)."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from typing import Any

import pandas as pd

from wiqaya.capacity.slots import sites
from wiqaya.common import config as C
from wiqaya.outreach.render import label, render, visit_label

CALLER = "Noor"  # synthetic care-team name used in call/CHW scripts


def _ddmm(d: date) -> str:
    return d.strftime("%d/%m")


def _site_name(site_id: str) -> str:
    c = C.clinics().get(site_id)
    if c:
        return str(c["name"])
    v = C.van_stops().get(site_id)
    return f"Mobile Screening Van – {v['label']}" if v else site_id


def preview(flag: dict[str, Any], people: pd.DataFrame, gaps: pd.DataFrame, flags: pd.DataFrame,
            channel: str | None = None, language: str | None = None) -> dict[str, Any]:  # fmt: skip
    """Rendered message for a flag. Cascade messages are previews only until a clinician approves."""
    ppl = people.set_index("id")
    person = ppl.loc[flag["person_id"]]
    recipient_id = flag.get("recipient_id") or flag["person_id"]
    recipient = ppl.loc[recipient_id]
    channels = (
        json.loads(flag["channels"]) if isinstance(flag.get("channels"), str) else list(flag.get("channels") or [])
    )
    channel = channel or (channels[0] if channels else "chw_script")
    language = language or flag.get("language_plan") or "en"
    audience = flag.get("audience") or "adult"
    pathway = flag.get("message_pathway") or "household_bundle"
    site_id = str(flag["site_id"]) if flag.get("site_id") else ""
    slot_date = (
        pd.to_datetime(flag["date"]).date() if flag.get("date") is not None and not pd.isna(flag.get("date")) else None
    )
    slot_time = flag.get("time") or "09:00"
    S = sites()
    is_van = bool(site_id) and S[site_id].kind == "van"
    # Household bundle: other household members with a slot at the same site on the same day.
    hh = flags[
        (flags.household_id == flag["household_id"]) & (flags.site_id == site_id) & (flags.date == flag.get("date"))
    ]
    members = [ppl.loc[pid, "given"] for pid in hh.person_id] if site_id else []
    bundled = len(members) > 1 and pathway not in ("cascade_family",)
    if bundled and audience != "caregiver_of_elder":
        pathway, audience = "household_bundle", "adult"
    if is_van and pathway not in ("cascade_family",):
        pathway, audience = "mobile_van", "adult"
    if slot_date:
        options = [f"{_ddmm(slot_date)} {slot_time}"]
        for k in (1, 2):
            d2 = slot_date + timedelta(days=k)
            options.append(f"{_ddmm(d2)} {slot_time}")
        slot_options = "; ".join(options)
        slot_short = f"{_ddmm(slot_date)} {slot_time}"
    else:
        slot_options = slot_short = label(language, "words", "or")  # waitlist: no slot yet
    top_gap = gaps[(gaps.person_id == flag["person_id"]) & (gaps.rule_id == flag["top_rule_id"])]
    milestone = None
    if len(top_gap):
        try:
            milestone = json.loads(top_gap.iloc[0].evidence).get("milestone")
        except (TypeError, ValueError):
            milestone = None
    clinic = _site_name(site_id) if site_id else _site_name(person.assigned_clinic_id)
    rule_pathway = flag.get("message_pathway") or "household_bundle"
    values = {
        "recipient_first_name": recipient.given,
        "child_first_name": person.given,
        "visit_label": visit_label(language, milestone),
        "clinic_name": clinic,
        "clinic_short": clinic.split("–")[-1].strip()[:14],
        "slot_options": slot_options,
        "slot_short": slot_short,
        "n_members": str(len(members)),
        "member_names": (" & ".join(members) if members else person.given),
        "van_location": C.van_stops()[site_id]["label"] if is_van else clinic,
        "van_date": _ddmm(slot_date) if slot_date else "",
        "caller_name": CALLER,
        "pathway_label": label(language, "pathway_labels", rule_pathway),
        "until_date": _ddmm((slot_date or C.t0()) + timedelta(days=30)),
    }
    send_from = datetime.combine((slot_date or C.t0()) - timedelta(days=5), time(10, 0))
    cascade = flag.get("top_pathway") == "cascade" or rule_pathway == "cascade_family"
    r = render(pathway=pathway, audience=audience, channel=channel, language=language, values=values,
               send_from=send_from, clinician_approval_required=cascade)  # fmt: skip
    out = r.as_dict()
    out.update({
        "flag_id": flag["flag_id"], "recipient_id": recipient_id, "household_bundled": bundled,
        "bundled_members": members if bundled else [], "site_id": site_id, "slot": slot_short if slot_date else None,
        "available_channels": channels, "language_supported": bool(flag.get("language_supported", True)),
        "contact_reason": flag.get("contact_reason"),
        "status": "blocked_until_clinician_approval_and_index_consent" if cascade else "ready_for_review",
        "label": "Simulated cohort",
    })  # fmt: skip
    if not out["language_supported"]:
        out["timing_notes"] = [*out["timing_notes"], "preferred language not in library: English used (documented gap)"]
    return out
