"""Who to contact, on which channel and in which language (PROMPT.md §6.5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from wiqaya.outreach.library import load_library
from wiqaya.simulate.response import reachable

CHANNEL_CONSENT = {"whatsapp": "contact_whatsapp", "sms": "contact_sms", "call_script": "contact_call",
                   "chw_script": "chw_visit"}  # fmt: skip


@dataclass(frozen=True)
class ContactPlan:
    person_id: str
    recipient_id: str  # the person messaged (a parent for minors, a caregiver for some elders)
    audience: str  # parent | adult | caregiver_of_elder
    language: str  # message language (falls back to en if not in the library)
    language_supported: bool
    channels: tuple[str, ...]  # in order; may be empty = cannot be contacted
    reason: str


class Planner:
    def __init__(self, t: dict[str, pd.DataFrame], as_of: date) -> None:
        self.people = t["people"].set_index("id")
        self.as_of = as_of
        cons = t["consents"]
        self.granted = {(r.person_id, r.category) for r in cons.itertuples(index=False) if r.status == "granted"}
        self.langs = set(load_library().languages())
        rel = t["relationships"]
        self.parents: dict[str, list[str]] = {}
        for r in rel[rel.type.isin(["mother", "father"])].sort_values("type", ascending=False).itertuples(index=False):
            self.parents.setdefault(r.person_id, []).append(r.related_person_id)
        self.adults_in_hh: dict[str, list[str]] = {}
        for p in t["people"].itertuples(index=False):
            if (as_of - p.birth_date).days / 365.25 >= 18:
                self.adults_in_hh.setdefault(p.household_id, []).append(p.id)
        self.pref_order: dict[str, list[str]] = {}

    def age(self, pid: str) -> float:
        return float((self.as_of - self.people.loc[pid, "birth_date"]).days / 365.25)

    def channels_for(self, pid: str) -> tuple[str, ...]:
        p = self.people.loc[pid]
        order = ["whatsapp", "sms", "call_script", "chw_script"]
        if p.housing_type == "labour_accommodation" and p.phone_type != "smartphone":
            order = ["sms", "chw_script", "call_script"]
        return tuple(ch for ch in order if (pid, CHANNEL_CONSENT[ch]) in self.granted and reachable(p.phone_type, ch))

    def plan(self, pid: str) -> ContactPlan:
        p = self.people.loc[pid]
        age = self.age(pid)
        recipient, audience, reason = pid, "adult", "self"
        if age < 18:
            audience = "parent"
            cands = [x for x in self.parents.get(pid, []) if x in self.people.index]
            cands += [a for a in self.adults_in_hh.get(p.household_id, []) if a not in cands]
            if cands:
                recipient, reason = cands[0], "minor: parent/guardian is contacted"
        elif age >= 70:
            carers = [a for a in self.adults_in_hh.get(p.household_id, []) if a != pid and self.age(a) < 65]
            if carers:
                recipient, audience, reason = carers[0], "caregiver_of_elder", "older adult: caregiver is contacted"
        r = self.people.loc[recipient]
        lang = r.preferred_language
        supported = lang in self.langs
        return ContactPlan(pid, recipient, audience, lang if supported else "en", supported,
                           self.channels_for(recipient), reason)  # fmt: skip

    def as_records(self, pids: list[str]) -> dict[str, dict[str, Any]]:
        out = {}
        for pid in pids:
            cp = self.plan(pid)
            out[pid] = {"recipient_id": cp.recipient_id, "audience": cp.audience, "language": cp.language,
                        "language_supported": cp.language_supported, "channels": list(cp.channels),
                        "reason": cp.reason}  # fmt: skip
        return out
