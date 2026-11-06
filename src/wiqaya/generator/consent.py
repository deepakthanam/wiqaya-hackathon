"""Consent and contact preferences (PROMPT.md §4 step 7)."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from wiqaya.common import config as C
from wiqaya.generator.entities import Cohort, Consent, ContactPreference

CATEGORIES = ("clinical_data", "family_links", "genomic", "contact_sms", "contact_whatsapp",
              "contact_call", "chw_visit")  # fmt: skip


def build_consents(c: Cohort, rng: np.random.Generator, t0: date) -> None:
    probs = C.cfg("population")["consent"]
    has_genomic = {g.person_id for g in c.genomic}
    n = 0
    fixed = {(x.person_id, x.category) for x in c.consents}  # personas may pre-set some
    for p in c.people:
        for cat in CATEGORIES:
            if (p.id, cat) in fixed:
                continue
            if cat == "genomic" and p.id not in has_genomic:
                continue
            if cat == "contact_whatsapp" and p.phone_type != "smartphone":
                continue
            if cat in ("contact_sms", "contact_call") and p.phone_type == "none":
                continue
            g, d = probs[cat]
            u = rng.random()
            status = "granted" if u < g else ("denied" if u < g + d else "not_asked")
            n += 1
            c.consents.append(Consent(f"consent-{n:07d}", p.id, cat, status,
                                      t0 - timedelta(days=int(rng.integers(30, 900)))))  # fmt: skip
    granted = {(x.person_id, x.category) for x in c.consents if x.status == "granted"}
    have_pref = {x.person_id for x in c.preferences}
    for p in c.people:
        if p.id in have_pref:
            continue
        order = [ch for ch, cat in (("whatsapp", "contact_whatsapp"), ("sms", "contact_sms"),
                                    ("call_script", "contact_call"), ("chw_script", "chw_visit"))
                 if (p.id, cat) in granted]  # fmt: skip
        c.preferences.append(ContactPreference(p.id, order))
