"""History period simulation (PROMPT.md §4 step 5): the 24 months before T0.

Produces encounters, observations, immunisations, detections (conditions) and baseline-policy invitations
with responses. This is the only data Wiqaya's models train on.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np

from wiqaya.common import config as C
from wiqaya.common.geo import haversine_km
from wiqaya.generator.entities import (
    Cohort,
    Communication,
    Condition,
    Encounter,
    Immunization,
    Observation,
    Person,
)
from wiqaya.simulate.response import Contact, p_book, reachable

M = 30.4375


def age_on(p: Person, d: date) -> float:
    return (d - p.birth_date).days / 365.25


class Recorder:
    """Appends records with sequential ids. Shared by the history builder and the simulator."""

    def __init__(self, c: Cohort, prefix: str = "") -> None:
        self.c = c
        self.prefix = prefix
        self.n: dict[str, int] = {}

    def nid(self, kind: str) -> str:
        self.n[kind] = self.n.get(kind, 0) + 1
        return f"{kind}-{self.prefix}{self.n[kind]:07d}"

    def encounter(self, pid: str, d: date, typ: str, clinic: str, attended: bool, via: str) -> Encounter:
        e = Encounter(self.nid("enc"), pid, d, typ, clinic, attended, via)
        self.c.encounters.append(e)
        return e

    def obs(self, pid: str, d: date, key: str, value: float, enc: str | None) -> None:
        self.c.observations.append(Observation(self.nid("obs"), pid, d, key, round(float(value), 2), enc))

    def condition(self, pid: str, key: str, d: date, verification: str = "confirmed") -> None:
        self.c.conditions.append(Condition(self.nid("cond"), pid, key, d, verification))

    def imm(self, pid: str, vaccine: str, d: date) -> None:
        self.c.immunizations.append(Immunization(self.nid("imm"), pid, vaccine, d))


class Screener:
    """Generates screening results from latent truth and records detections."""

    def __init__(self, c: Cohort, rec: Recorder, rng: np.random.Generator) -> None:
        self.c, self.rec, self.rng = c, rec, rng
        b = C.cfg("population")["behaviour"]
        self.noise, self.sens, self.spec = b["measurement_noise"], b["test_sensitivity"], b["test_specificity"]
        self.known: dict[str, set[str]] = {}
        for cond in c.conditions:
            self.known.setdefault(cond.person_id, set()).add(cond.key)
        self.last: dict[tuple[str, str], date] = {}
        self.detections: list[tuple[str, str, date]] = []

    def note(self, pid: str, key: str, d: date) -> None:
        prev = self.last.get((pid, key))
        if prev is None or d > prev:
            self.last[(pid, key)] = d

    def _detect(self, pid: str, key: str, d: date) -> None:
        if key not in self.known.setdefault(pid, set()):
            self.known[pid].add(key)
            self.rec.condition(pid, key, d)
            self.detections.append((pid, key, d))

    def adult_panel(self, p: Person, d: date, enc: str | None, full: bool = True) -> list[str]:
        """Run the age/sex-appropriate panel. Returns keys measured."""
        rng, lt = self.rng, self.c.latent[p.id]
        age = age_on(p, d)
        done: list[str] = []
        bmi = (lt.get("bmi") or 25.0) + rng.normal(0, self.noise["bmi"])
        self.rec.obs(p.id, d, "bmi", bmi, enc)
        done.append("bmi")
        htn = lt.get("hypertension") or lt.get("hypertension_diagnosed")
        sbp = rng.normal(146, 10) if htn else rng.normal(119, 10)
        dbp = rng.normal(92, 7) if htn else rng.normal(76, 7)
        if htn and rng.random() > self.sens["bp"]:
            sbp, dbp = rng.normal(132, 5), rng.normal(82, 4)
        sbp += rng.normal(0, self.noise["sbp"])
        dbp += rng.normal(0, self.noise["dbp"])
        self.rec.obs(p.id, d, "sbp", sbp, enc)
        self.rec.obs(p.id, d, "dbp", dbp, enc)
        done.append("sbp")
        if (sbp >= 140 or dbp >= 90) and lt.get("hypertension") and rng.random() < 0.5:
            self._detect(p.id, "hypertension", d)
            lt["hypertension"] = False
            lt["hypertension_diagnosed"] = True
        if not full:
            return done
        if age >= 30 or bmi >= 25:
            if lt.get("undiagnosed_t2d") or lt.get("t2d_diagnosed"):
                v = rng.normal(7.5, 0.9) if rng.random() < self.sens["hba1c_t2d"] else rng.uniform(6.0, 6.4)
                v = max(v, 6.0)
            elif lt.get("prediabetes"):
                v = rng.uniform(5.7, 6.4) if rng.random() < self.sens["hba1c_pre"] else rng.uniform(5.3, 5.6)
            else:
                v = min(5.6, rng.normal(5.25, 0.2))
            v += rng.normal(0, self.noise["hba1c"] / 3)
            self.rec.obs(p.id, d, "hba1c", v, enc)
            self.note(p.id, "hba1c", d)
            done.append("hba1c")
            if v >= 6.5 and lt.get("undiagnosed_t2d"):
                self._detect(p.id, "t2d", d)
                lt["undiagnosed_t2d"] = False
                lt["t2d_diagnosed"] = True
            elif 5.7 <= v < 6.5 and lt.get("prediabetes"):
                self._detect(p.id, "prediabetes", d)
        if age >= 35:
            if lt.get("fh_carrier"):
                ldl = rng.normal(225, 30)
            elif lt.get("dyslipidaemia"):
                ldl = rng.normal(165, 20)
            else:
                ldl = rng.normal(110, 22)
            ldl += rng.normal(0, self.noise["ldl"])
            self.rec.obs(p.id, d, "ldl", ldl, enc)
            self.note(p.id, "ldl", d)
            done.append("ldl")
            if ldl >= 190 and lt.get("dyslipidaemia"):
                self._detect(p.id, "dyslipidaemia", d)
                lt["dyslipidaemia"] = False
                lt["dyslipidaemia_diagnosed"] = True
                if lt.get("fh_carrier") and rng.random() < 0.3:
                    self._detect(p.id, "fh", d)
                    lt["fh_diagnosed"] = True
        if p.sex == "female" and 21 <= age <= 65:
            last = self.last.get((p.id, "cervical"))
            if last is None or (d - last).days > 30 * M:
                key = "hpv" if age >= 30 and rng.random() < 0.5 else "cytology"
                pos = (
                    (rng.random() < self.sens["cervical"])
                    if lt.get("cervical_cin2plus")
                    else (rng.random() > self.spec["cervical"])
                )
                self.rec.obs(p.id, d, key, 1.0 if pos else 0.0, enc)
                self.note(p.id, "cervical", d)
                done.append(key)
                if pos and lt.get("cervical_cin2plus"):
                    self._detect(p.id, "cin2plus", d)
                    lt["cervical_cin2plus"] = False
        if 45 <= age <= 75:
            last = self.last.get((p.id, "fit"))
            if last is None or (d - last).days > 11 * M:
                pos = (
                    (rng.random() < self.sens["fit"])
                    if lt.get("colorectal_advanced_neoplasia")
                    else (rng.random() > self.spec["fit"])
                )
                self.rec.obs(p.id, d, "fit", 1.0 if pos else 0.0, enc)
                self.note(p.id, "fit", d)
                done.append("fit")
                if pos and lt.get("colorectal_advanced_neoplasia"):
                    self._detect(p.id, "colorectal_neoplasia", d)
                    lt["colorectal_advanced_neoplasia"] = False
        if p.sex == "female" and 40 <= age <= 74:
            last = self.last.get((p.id, "mammogram"))
            if last is None or (d - last).days > 22 * M:
                birads = float(rng.choice([1, 2, 3, 4], p=[0.6, 0.35, 0.03, 0.02]))
                self.rec.obs(p.id, d, "mammogram", birads, enc)
                self.note(p.id, "mammogram", d)
                done.append("mammogram")
        return done


class HistoryBuilder:
    def __init__(self, c: Cohort, rng: np.random.Generator, t0: date) -> None:
        self.c, self.rng, self.t0 = c, rng, t0
        self.p = C.cfg("population")
        self.sim = C.cfg("simulation")
        self.sched = C.cfg("schedules")
        self.start = t0 - timedelta(days=int(self.p["history_months"] * M))
        self.rec = Recorder(c)
        self.screen = Screener(c, self.rec, rng)
        self.clinics = C.clinics()
        self.granted = {(x.person_id, x.category) for x in c.consents if x.status == "granted"}
        self.hh = {h.id: h for h in c.households}

    def _rand_date(self, a: date, b: date) -> date:
        span = max(1, (b - a).days)
        return a + timedelta(days=int(self.rng.integers(0, span)))

    def _distance(self, p: Person) -> float:
        cl = self.clinics[p.assigned_clinic_id]
        return haversine_km(p.lat, p.lon, cl["lat"], cl["lon"])

    # ------------------------------------------------------------------ children
    def child(self, p: Person) -> None:
        rng, beh = self.rng, self.p["behaviour"]["wcv_attend_prob"]
        hh = self.hh[p.household_id]
        attend_p = beh["emirati"] if p.nationality_group == "emirati" else beh["base"]
        attend_p = float(np.clip(attend_p + rng.normal(0, 0.1), 0.2, 0.97))
        lt = self.c.latent[p.id]
        # Immunisations: doses due before T0, given with the child's engagement level.
        counts: dict[str, int] = {}
        for dose in self.sched["immunisation"]["doses"]:
            target = p.birth_date + timedelta(days=int(dose["age_months"] * M))
            if target >= self.t0:
                continue
            give_p = 0.93 if target < self.start else attend_p + 0.1
            if rng.random() < give_p:
                d = target + timedelta(days=int(rng.integers(0, 40)))
                if d < self.t0:
                    self.rec.imm(p.id, dose["vaccine"], d)
                    counts[dose["vaccine"]] = counts.get(dose["vaccine"], 0) + 1
        # Well-child visits in the history window.
        w = self.sched["wcv"]
        milestones = [(k, float(m)) for k, m in w["visits"].items()]
        milestones += [(f"y{y}", y * 12.0) for y in range(w["yearly_from_years"], w["yearly_to_years"] + 1)]
        clinic = p.assigned_clinic_id
        for key, m in milestones:
            target = p.birth_date + timedelta(days=int(m * M))
            if not (self.start <= target < self.t0 - timedelta(days=10)):
                continue
            if rng.random() < attend_p:
                d = min(self.t0 - timedelta(days=1), target + timedelta(days=int(rng.integers(-7, 30))))
                e = self.rec.encounter(p.id, d, "wcv", clinic, True, "self")
                if m >= 24:
                    pct = rng.uniform(95, 99.5) if lt["child_high_bmi"] else rng.uniform(5, 94.5)
                    self.rec.obs(p.id, d, "bmi_pct", pct, e.id)
                    if lt["child_high_bmi"] and rng.random() < 0.4:
                        fu = d + timedelta(days=int(rng.integers(60, 170)))
                        if fu < self.t0:
                            self.rec.encounter(p.id, fu, "chronic_review", clinic, True, "self")
                if m in (9, 18, 30):
                    refer = (
                        (rng.random() < self.p["behaviour"]["test_sensitivity"]["dev"])
                        if lt["developmental_delay"]
                        else (rng.random() > self.p["behaviour"]["test_specificity"]["dev"])
                    )
                    self.rec.obs(p.id, d, "dev_screen", 1.0 if refer else 0.0, e.id)
                    if refer and lt["developmental_delay"]:
                        self.screen._detect(p.id, "developmental_delay", d)
                if m in (18, 24):
                    refer = rng.random() < 0.05
                    self.rec.obs(p.id, d, "autism_screen", 1.0 if refer else 0.0, e.id)
            elif rng.random() < 0.5:
                d = target + timedelta(days=int(rng.integers(0, 20)))
                if d < self.t0:
                    self.rec.encounter(p.id, d, "wcv", clinic, False, "invite_baseline")
        _ = hh

    # ------------------------------------------------------------------ adults
    def legacy_tests(self, p: Person) -> None:
        """Pre-history results (1-6 years before the history start), so long intervals are visible."""
        rng = self.rng
        p_leg = 0.6 if p.has_regular_clinic else 0.25
        if p.role == "worker":
            p_leg = 0.15
        if rng.random() > p_leg:
            return
        d = self.start - timedelta(days=int(rng.integers(30, 6 * 365)))
        if age_on(p, d) < 21:
            return
        e = self.rec.encounter(p.id, d, "adult_screen", p.assigned_clinic_id, True, "self")
        self.screen.adult_panel(p, d, e.id)

    def invite(self, p: Person, d: date, channel: str, language: str, policy: str, generic: bool,
               events: list[tuple[date, str, str, bool, bool]]) -> None:  # fmt: skip
        rng = self.rng
        lt = self.c.latent[p.id]
        contact = Contact(channel, language, self._distance(p), generic=generic)
        pb = p_book(p, lt, contact, self.sim["response_model"])
        booked = rng.random() < pb
        tid = f"HISTORY_{policy.upper()}_{channel.upper()}"
        self.c.communications.append(Communication(
            self.rec.nid("comm"), p.id, p.household_id, tid, language, channel, d,
            "booked" if booked else ("declined" if rng.random() < 0.08 else "none"), policy, "adult_screening"))  # fmt: skip
        if booked:
            visit = d + timedelta(days=int(rng.integers(3, 21)))
            if visit >= self.t0:
                return
            shows = bool(rng.random() < self.sim["response_model"]["show_given_booked"])
            via = "invite_baseline" if policy == "baseline" else "self"
            events.append((visit, "adult_screen", via, shows, True))

    def adult(self, p: Person) -> None:
        rng, beh = self.rng, self.p["behaviour"]
        self.legacy_tests(p)
        years = (self.t0 - self.start).days / 365.25
        # (date, encounter type, scheduled_via, attended, full panel)
        events: list[tuple[date, str, str, bool, bool]] = []
        if self.screen.known.get(p.id, set()) & {"t2d", "hypertension", "dyslipidaemia"}:
            for _ in range(int(rng.poisson(1.6 * years))):
                events.append((self._rand_date(self.start, self.t0), "chronic_review", "self", True,
                               "t2d" in self.screen.known[p.id] or bool(rng.random() < 0.5)))  # fmt: skip
        rate = beh["walk_in_screen_rate_per_year"]["has_clinic" if p.has_regular_clinic else "no_clinic"]
        for _ in range(int(rng.poisson(rate * years))):
            events.append((self._rand_date(self.start, self.t0), "adult_screen", "walk_in", True, True))
        if p.role == "worker" and rng.random() < 0.12:
            events.append((self._rand_date(self.start, self.t0), "mobile_van", "walk_in", True,
                           bool(rng.random() < 0.5)))  # fmt: skip
        for _ in range(int(rng.poisson(beh["acute_visit_rate_per_year"] * years))):
            events.append((self._rand_date(self.start, self.t0), "acute", "self", True, False))
        # Baseline-policy invitations: generic SMS in Arabic or English.
        if p.phone_type != "none" and (p.id, "contact_sms") in self.granted:
            lang = "ar" if p.preferred_language == "ar" else "en"
            for y in range(int(round(years))):
                if rng.random() < self.sim["history"]["baseline_invite_prob_per_year"]:
                    a = self.start + timedelta(days=int(365.25 * y))
                    self.invite(p, self._rand_date(a, min(self.t0, a + timedelta(days=365))), "sms", lang,
                                "baseline", True, events)  # fmt: skip
        # Randomised channel invitations (for the uplift model).
        if rng.random() < self.sim["history"]["random_invite_prob"]:
            options = [ch for ch, cat in (("whatsapp", "contact_whatsapp"), ("sms", "contact_sms"),
                                          ("call_script", "contact_call"), ("chw_script", "chw_visit"))
                       if (p.id, cat) in self.granted and reachable(p.phone_type, ch)]  # fmt: skip
            if options:
                ch = options[int(rng.integers(len(options)))]
                lang = p.preferred_language if rng.random() < 0.5 else ("ar" if p.preferred_language == "ar" else "en")
                self.invite(p, self._rand_date(self.start, self.t0), ch, lang, "random", False, events)
        acute_bp = beh["opportunistic_bp_at_acute"]
        for d, typ, via, attended, full in sorted(events):
            e = self.rec.encounter(p.id, d, typ, p.assigned_clinic_id, attended, via)
            if not attended:
                continue
            if typ == "acute":
                if rng.random() < acute_bp:
                    self.screen.adult_panel(p, d, e.id, full=False)
            else:
                self.screen.adult_panel(p, d, e.id, full=full)

    def build(self) -> None:
        for p in self.c.people:
            if p.pinned:
                continue
            if age_on(p, self.start) < 18:
                self.child(p)
            if age_on(p, self.t0) >= 18:
                self.adult(p)

    def summary(self) -> dict[str, Any]:
        return {"detections": len(self.screen.detections)}
