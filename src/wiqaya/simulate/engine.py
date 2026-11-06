"""12-week evaluation simulator (PROMPT.md §6.6): baseline vs Wiqaya with common random numbers.

Both policies get the same capacity, the same invitation budget and the SAME random draws per person
(`crn`). Only their choices differ: who is contacted, in what order, how, in which language, bundled or not.
The response model reads hidden latent parameters; Wiqaya's models never see them.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import pandas as pd

from wiqaya.capacity.slots import open_days, sites
from wiqaya.common import config as C
from wiqaya.common.geo import haversine_km
from wiqaya.simulate.response import Contact, p_attend, reachable

AGE_SEX_PATHWAYS = {"wcv", "immunisation", "developmental", "adult_screening"}  # today's baseline: age/sex rules
RULE_LATENT: dict[
    str, list[tuple[str, str, str | None]]
] = {  # rule -> [(latent key, sensitivity key, specificity key or None)]
    "ADULT_T2D_SCREEN": [("undiagnosed_t2d", "hba1c_t2d", None), ("prediabetes", "hba1c_pre", None)],
    "FOLLOWUP_PREDIABETES": [("undiagnosed_t2d", "hba1c_t2d", None), ("prediabetes", "hba1c_pre", None)],
    "ADULT_BP_SCREEN": [("hypertension", "bp", None)],
    "FOLLOWUP_BP_ELEVATED": [("hypertension", "bp", None)],
    "ADULT_LIPID_CVD": [("dyslipidaemia", "lipid", None)],
    "CASCADE_FH": [("fh_carrier", "lipid", None)],
    "CERVICAL_SCREEN": [("cervical_cin2plus", "cervical", "cervical")],
    "COLORECTAL_SCREEN": [("colorectal_advanced_neoplasia", "fit", "fit")],
    "DEV_SCREEN": [("developmental_delay", "dev", "dev")],
    "AUTISM_SCREEN": [("developmental_delay", "autism", "autism")],
}
LATENT_KEYS = sorted({k for v in RULE_LATENT.values() for k, _, _ in v})


def crn(seed: int, key: str, k: int) -> float:
    """Common random number in [0, 1): identical for both policies for the same (person, draw index)."""
    h = hashlib.sha256(f"{seed}|{key}|{k}".encode()).digest()
    return int.from_bytes(h[:8], "big") / 2**64


def _bool(x: Any) -> bool:
    return str(x).lower() == "true"


def latent_table(raw: pd.DataFrame) -> dict[str, dict[str, Any]]:
    out = {}
    for r in raw.to_dict("records"):
        lt: dict[str, Any] = {k: _bool(r.get(k)) for k in LATENT_KEYS}
        lt["response_propensity_by_channel"] = json.loads(r["response_propensity_by_channel"])
        for k in ("language_sensitivity", "distance_sensitivity", "bundle_effect"):
            lt[k] = float(r[k])
        out[r["person_id"]] = lt
    return out


@dataclass
class Item:
    person_id: str
    recipient_id: str
    household_id: str
    slot_type: str
    rules: list[str]
    gap_ids: list[str]
    pathways: list[str]
    order: float
    site_id: str
    week: int | None
    channels: list[str]
    language: str
    generic: bool
    high_priority: bool
    bundle_key: str | None = None
    touches: int = 0
    done: bool = False
    declined: bool = False
    attended_on: date | None = None
    detections: list[str] = field(default_factory=list)
    false_positive: bool = False


def channel_sequence(consented: list[str]) -> list[str]:
    """Touch sequence: up to two text/call touches, then a CHW visit after 2 non-responses (if consented)."""
    text = [c for c in consented if c != "chw_script"]
    seq = (text[:2] if len(text) >= 2 else text * 2)[:2]
    if "chw_script" in consented:
        seq.append("chw_script")
    elif text:
        seq.append(text[0])
    return seq


class Simulator:
    def __init__(self, t: dict[str, pd.DataFrame], gaps: pd.DataFrame, flags: pd.DataFrame, assignments: pd.DataFrame,
                 buckets: pd.DataFrame, latent: dict[str, dict[str, Any]], params: dict[str, Any], seed: int) -> None:  # fmt: skip
        self.t, self.gaps, self.flags, self.assign, self.buckets = t, gaps, flags, assignments, buckets
        self.latent, self.params, self.seed = latent, params, seed
        self.sim = C.cfg("simulation")
        self.beh = C.cfg("population")["behaviour"]
        self.people = t["people"].set_index("id")
        self.sites = sites()
        self.start = date.fromisoformat(self.sim["evaluation"]["start"])
        self.n_weeks = int(self.sim["evaluation"]["weeks"])
        cons = t["consents"]
        self.granted = {(r.person_id, r.category) for r in cons.itertuples(index=False) if r.status == "granted"}

    # ------------------------------------------------------------------ policies
    def baseline_items(self) -> list[Item]:
        g = self.gaps[self.gaps.pathway.isin(AGE_SEX_PATHWAYS)]
        items = []
        for pid, pg in g.groupby("person_id", sort=True):
            p = self.people.loc[pid]
            recipient = pid
            if p.role == "child":
                fl = self.flags[self.flags.person_id == pid]
                recipient = pid
                if len(fl) and "recipient_id" in fl:
                    recipient = fl.recipient_id.iloc[0]
            r = self.people.loc[recipient] if recipient in self.people.index else p
            ok = r.phone_type != "none" and (recipient, "contact_sms") in self.granted
            lang = "ar" if r.preferred_language == "ar" else "en"
            items.append(Item(pid, recipient, p.household_id, self._slot_type(pg), sorted(pg.rule_id), sorted(pg.id),
                              sorted(pg.pathway.unique()), float(pd.Timestamp(pg.due_date.min()).value),
                              p.assigned_clinic_id, None, ["sms"] if ok else [], lang, True, False))  # fmt: skip
        items.sort(key=lambda i: (i.order, i.person_id))
        for i in items[: len(items) // 3]:
            i.high_priority = True
        return items

    def _slot_type(self, pg: pd.DataFrame) -> str:
        from wiqaya.rules.schema import load_rules

        rules = {r.id: r for r in load_rules()}
        types = [rules[r].slot_type for r in pg.rule_id]
        return "child" if "child" in types else ("women" if "women" in types else "adult")

    def wiqaya_items(self) -> tuple[list[Item], dict[str, Any]]:
        a = self.assign.set_index("flag_id") if len(self.assign) else pd.DataFrame()
        gaps_by = self.gaps.groupby("person_id")
        items, rejected = [], []
        rate = self.sim["policies"]["wiqaya"]["reviewer_accept_rate"]
        for f in self.flags.sort_values("rank").itertuples(index=False):
            # Simulated human review: accept ~90%, reject ~10% at random (logged).
            if crn(self.sim["seeds"]["reviewer"], f.flag_id, 0) > rate:
                rejected.append(f.flag_id)
                continue
            pg = gaps_by.get_group(f.person_id)
            site, week = self.people.loc[f.person_id, "assigned_clinic_id"], None
            if f.flag_id in a.index:
                site, week = a.loc[f.flag_id, "site_id"], int(a.loc[f.flag_id, "week"])
            channels = channel_sequence(json.loads(f.channels) if isinstance(f.channels, str) else list(f.channels))
            items.append(Item(f.person_id, f.recipient_id, f.household_id, f.slot_type, sorted(pg.rule_id), sorted(pg.id),
                              sorted(pg.pathway.unique()), float(f.rank), site, week, channels, f.language_plan, False,
                              f.band == "high", bundle_key=None))  # fmt: skip
        # Household bundles: members assigned to the same site and week share one message.
        groups: dict[tuple[str, str, int], list[Item]] = defaultdict(list)
        for it in items:
            if it.week is not None:
                groups[(it.household_id, it.site_id, it.week)].append(it)
        for key, g in groups.items():
            if len(g) > 1:
                for it in g:
                    it.bundle_key = "|".join(map(str, key))
                    it.recipient_id = g[0].recipient_id
        return items, {"reviewed": len(self.flags), "rejected": len(rejected), "rejected_ids": rejected[:50]}

    # ------------------------------------------------------------------ run
    def run(self, policy: str) -> dict[str, Any]:
        pcfg = self.sim["policies"]
        if policy == "baseline":
            items, review = self.baseline_items(), {"reviewed": 0, "rejected": 0}
            max_touches = pcfg["baseline"]["max_touches"]
        else:
            items, review = self.wiqaya_items()
            max_touches = pcfg["wiqaya"]["max_touches"]
        cap = {(r.site_id, r.week, r.slot_type): int(r.capacity) for r in self.buckets.itertuples(index=False)}
        budget = {k: math.ceil(v * pcfg["invites_per_slot"]) for k, v in cap.items()}
        comms: list[dict[str, Any]] = []
        encounters: list[dict[str, Any]] = []
        bundles: dict[str, list[Item]] = defaultdict(list)
        for x in items:
            if x.bundle_key:
                bundles[x.bundle_key].append(x)
        for w in range(self.n_weeks):
            week_start = self.start + timedelta(days=7 * w)
            handled: set[str] = set()
            for it in items:
                if it.done or it.declined or it.touches >= max_touches or not it.channels or it.person_id in handled:
                    continue
                if it.week is not None and w < it.week:
                    continue
                group = bundles[it.bundle_key] if it.bundle_key else [it]
                group = [x for x in group if not (x.done or x.declined)]
                site = it.site_id
                st_keys = [(site, w, x.slot_type) for x in group]
                if any(budget.get(k, 0) <= 0 for k in st_keys):
                    # Try the nearest other site with budget (both policies may spill over).
                    continue
                for k in st_keys:
                    budget[k] -= 1
                ch = it.channels[min(it.touches, len(it.channels) - 1)]
                recipient = it.recipient_id if it.recipient_id in self.people.index else it.person_id
                rp = self.people.loc[recipient]
                person = self.people.loc[it.person_id]
                s = self.sites[site]
                dist = haversine_km(person.lat, person.lon, s.lat, s.lon)
                contact = Contact(ch, it.language, dist, bundled=len(group) > 1, van=s.kind == "van",
                                  touch_index=it.touches, generic=it.generic)  # fmt: skip
                lt = self.latent[recipient]
                prob = p_attend(rp, lt, contact, self.params) if reachable(rp.phone_type, ch) else 0.0
                key = it.bundle_key or it.person_id
                u = crn(self.seed, key, it.touches)
                success = u < prob
                comms.append({"policy": policy, "person_id": it.person_id, "recipient_id": recipient,
                              "household_id": it.household_id, "channel": ch, "language": it.language,
                              "week": w, "sent_at": week_start, "bundled": len(group) > 1, "members": len(group),
                              "van": s.kind == "van", "response": "booked" if success else "none", "simulated": True})  # fmt: skip
                for x in group:
                    handled.add(x.person_id)
                    x.touches += 1
                if not success:
                    if crn(self.seed, key, 50 + it.touches) < 0.06:
                        comms[-1]["response"] = "declined"
                        for x in group:
                            x.declined = True
                    continue
                days = open_days(s, week_start) or [week_start]
                for j, x in enumerate(group):
                    bk = (site, w, x.slot_type)
                    if cap.get(bk, 0) <= 0:
                        continue
                    cap[bk] -= 1
                    x.done = True
                    x.attended_on = days[j % len(days)]
                    self._detect(x)
                    encounters.append({"policy": policy, "person_id": x.person_id, "date": x.attended_on, "site_id": site,
                                       "site_kind": s.kind, "rules": ",".join(x.rules), "detections": ",".join(x.detections),
                                       "false_positive": x.false_positive, "simulated": True})  # fmt: skip
        return {"items": items, "comms": pd.DataFrame(comms), "encounters": pd.DataFrame(encounters), "review": review}

    def _detect(self, it: Item) -> None:
        lt = self.latent[it.person_id]
        sens, spec = self.beh["test_sensitivity"], self.beh["test_specificity"]
        j = 0
        for rule in it.rules:
            for lkey, skey, spkey in RULE_LATENT.get(rule, []):
                j += 1
                u = crn(self.seed, it.person_id, 100 + j)
                if lt.get(lkey):
                    if u < sens[skey] and lkey not in it.detections:
                        it.detections.append(lkey)
                elif spkey and u > spec[spkey]:
                    it.false_positive = True
