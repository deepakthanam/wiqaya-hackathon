"""Household-first population builder (PROMPT.md §4 steps 1-3)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np

from wiqaya.common import config as C
from wiqaya.common.geo import haversine_km
from wiqaya.generator.entities import Cohort, Household, Person, Relationship

DEGREE = {
    "mother": 1, "father": 1, "child": 1, "sibling": 1, "spouse": 1,
    "grandparent": 2, "grandchild": 2, "aunt_uncle": 2, "niece_nephew": 2, "cousin": 3,
}  # fmt: skip
INVERSE = {"child": "parent", "sibling": "sibling", "spouse": "spouse", "grandparent": "grandchild",
           "aunt_uncle": "niece_nephew", "cousin": "cousin"}  # fmt: skip


def choice(rng: np.random.Generator, probs: dict[str, float]) -> str:
    keys = list(probs)
    p = np.array([probs[k] for k in keys], dtype=float)
    return str(keys[int(rng.choice(len(keys), p=p / p.sum()))])


def birth_from_age(t0: date, age_years: float) -> date:
    return t0 - timedelta(days=int(round(age_years * 365.25)))


class PopulationBuilder:
    def __init__(self, cohort: Cohort, rng: np.random.Generator, t0: date) -> None:
        self.c = cohort
        self.rng = rng
        self.t0 = t0
        self.p = C.cfg("population")
        self.names = C.names()
        self.districts = C.districts()
        self.clinics = C.clinics()
        self.hh_n = 0
        self.person_n = 0
        self.by_id: dict[str, Person] = {}

    # ------------------------------------------------------------------ helpers
    def _next_hh(self) -> str:
        self.hh_n += 1
        return f"hh-{self.hh_n:06d}"

    def _next_person(self) -> str:
        self.person_n += 1
        return f"p-{self.person_n:06d}"

    def location(self, district_id: str, spread: float = 0.012) -> tuple[float, float]:
        d = self.districts[district_id]
        return (
            round(float(d["lat"] + self.rng.normal(0, spread)), 5),
            round(float(d["lon"] + self.rng.normal(0, spread)), 5),
        )

    def nearest_clinic(self, lat: float, lon: float) -> str:
        best = min(self.clinics.values(), key=lambda c: haversine_km(lat, lon, c["lat"], c["lon"]))
        return str(best["id"])

    def given_name(self, group: str, sex: str) -> str:
        pool = self.names[group]["male" if sex == "male" else "female"]
        return str(pool[int(self.rng.integers(len(pool)))])

    def family_name(self, group: str) -> str:
        pool = self.names[group]["family"]
        return str(pool[int(self.rng.integers(len(pool)))])

    def _by_group(self, section: dict[str, Any], group: str, labour: bool = False) -> Any:
        if labour and "labour" in section:
            return section["labour"]
        return section.get(group, section.get("default"))

    def link(self, a: str, b: str, rel: str) -> None:
        """Record that b is a's <rel>, and the inverse."""
        self.c.relationships.append(Relationship(a, b, rel, DEGREE.get(rel, 1)))
        if rel in ("mother", "father"):
            inv = "child"
        else:
            inv = INVERSE[rel]
            if inv == "parent":
                inv = "mother" if self.by_id[a].sex == "female" else "father"
        self.c.relationships.append(Relationship(b, a, inv, DEGREE.get(inv, 1)))

    # ------------------------------------------------------------------ people
    def make_person(
        self,
        hh: Household,
        sex: str,
        age: float,
        role: str,
        family: str | None = None,
        labour: bool = False,
        pid: str | None = None,
        given: str | None = None,
        **overrides: Any,
    ) -> Person:
        rng, p, g = self.rng, self.p, hh.nationality_group
        lang = choice(rng, p["languages"][g]) if role != "child" else hh.primary_language
        lit = ["low", "med", "high"][int(rng.choice(3, p=self._by_group(p["literacy_proxy"], g, labour)))]
        if labour:
            phone_p = p["phone_type"]["labour"]
        elif age >= 70:
            phone_p = p["phone_type"]["elderly"]
        else:
            phone_p = p["phone_type"]["default"]
        phone = ["smartphone", "basic", "none"][int(rng.choice(3, p=phone_p))]
        if age < 13:
            phone = "none"  # children are reached through a parent
        ins_p = p["insurance_tier"]["emirati"] if g == "emirati" else self._by_group(p["insurance_tier"], g, labour)
        ins = ["Thiqa", "Enhanced", "Basic"][int(rng.choice(3, p=ins_p))]
        reg_p = p["has_regular_clinic"]["labour" if labour else ("emirati" if g == "emirati" else "default")]
        person = Person(
            id=pid or self._next_person(),
            household_id=hh.id,
            given=given or self.given_name(g, sex),
            family=family or self.family_name(g),
            sex=sex,
            birth_date=birth_from_age(self.t0, age) - timedelta(days=int(rng.integers(0, 60))),
            nationality_group=g,
            preferred_language=lang,
            literacy_proxy=lit,
            phone_type=phone,
            insurance_tier=ins,
            district_id=hh.district_id,
            has_regular_clinic=bool(rng.random() < reg_p),
            assigned_clinic_id=self.nearest_clinic(hh.lat, hh.lon),
            role=role,
            lat=hh.lat,
            lon=hh.lon,
        )
        for k, v in overrides.items():
            setattr(person, k, v)
        self.c.people.append(person)
        self.by_id[person.id] = person
        hh.size += 1
        return person

    def make_household(self, nationality: str, district: str, housing: str, hid: str | None = None) -> Household:
        lat, lon = self.location(district, 0.004 if housing == "labour_accommodation" else 0.012)
        lang_probs = self.p["languages"][nationality]
        hh = Household(
            id=hid or self._next_hh(),
            district_id=district,
            housing_type=housing,
            primary_language=max(lang_probs, key=lambda k: lang_probs[k]),
            nationality_group=nationality,
            lat=lat,
            lon=lon,
        )
        self.c.households.append(hh)
        return hh

    # ------------------------------------------------------------------ households
    def labour_household(self) -> list[Person]:
        rng, hp = self.rng, self.p["households"]
        g = choice(rng, hp["labour_nationality"])
        district = choice(rng, hp["labour_district"])
        hh = self.make_household(g, district, "labour_accommodation")
        size = int(rng.integers(hp["labour_size"]["min"], hp["labour_size"]["max"] + 1))
        out = []
        la = hp["labour_age"]
        for _ in range(size):
            sex = "male" if rng.random() < hp["labour_male_share"] else "female"
            age = float(rng.triangular(la["min"], la["mode"], la["max"]))
            # Workers in one unit often share a nationality but not always.
            if rng.random() < 0.25:
                hh_g = choice(rng, hp["labour_nationality"])
                old = hh.nationality_group
                hh.nationality_group = hh_g
                out.append(self.make_person(hh, sex, age, "worker", labour=True))
                hh.nationality_group = old
            else:
                out.append(self.make_person(hh, sex, age, "worker", labour=True))
        return out

    def family_household(self, g: str, sibling_of: Person | None = None) -> list[Person]:
        rng, hp = self.rng, self.p["households"]
        fam = hp["family"]
        if sibling_of is not None and rng.random() < self.p["siblings"]["same_district_prob"]:
            district = sibling_of.district_id
        else:
            weights = self.p["district_weights_family"].get(g, self.p["district_weights_family"]["default"])
            district = choice(rng, weights)
        housing = choice(rng, hp["housing_type_family"].get(g, hp["housing_type_family"]["default"]))
        hh = self.make_household(g, district, housing)
        members: list[Person] = []
        # Head adult (optionally a sibling of an adult elsewhere).
        if sibling_of is not None:
            sib_age = (self.t0 - sibling_of.birth_date).days / 365.25
            age1 = float(np.clip(sib_age + rng.normal(0, 4), fam["adult_age"]["min"], fam["adult_age"]["max"]))
            sex1 = "male" if rng.random() < 0.5 else "female"
        else:
            age1 = float(rng.uniform(fam["adult_age"]["min"], fam["adult_age"]["max"]))
            sex1 = "male" if rng.random() < 0.6 else "female"
        family = sibling_of.family if sibling_of is not None else self.family_name(g)
        head = self.make_person(hh, sex1, age1, "head", family=family)
        members.append(head)
        if sibling_of is not None:
            self.link(sibling_of.id, head.id, "sibling")
        spouse = None
        if rng.random() < fam["two_adult_prob"]:
            gap = float(rng.normal(fam["spouse_age_gap"]["mean"], fam["spouse_age_gap"]["sd"]))
            sex2 = "female" if sex1 == "male" else "male"
            age2 = age1 - gap if sex1 == "male" else age1 + gap
            age2 = float(np.clip(age2, 19, 75))
            spouse = self.make_person(hh, sex2, age2, "spouse", family=family if g != "western" else None)
            self.link(head.id, spouse.id, "spouse")
            members.append(spouse)
        mother = head if head.sex == "female" else spouse
        father = head if head.sex == "male" else spouse
        mother_age = (self.t0 - mother.birth_date).days / 365.25 if mother else age1
        probs = fam["children_count_probs"].get(g, fam["children_count_probs"]["default"])
        n_kids = int(rng.choice(len(probs), p=np.array(probs) / sum(probs)))
        lo = fam["mother_age_at_birth"]["min"]
        max_child_age = min(17.9, mother_age - lo)
        kids: list[Person] = []
        if max_child_age > 0:
            for _ in range(n_kids):
                kage = float(rng.uniform(0.02, max_child_age))
                sex = "male" if rng.random() < 0.51 else "female"
                kid = self.make_person(hh, sex, kage, "child", family=family)
                if mother:
                    self.link(kid.id, mother.id, "mother")
                if father:
                    self.link(kid.id, father.id, "father")
                kids.append(kid)
        for i, a in enumerate(kids):
            for b in kids[i + 1 :]:
                self.link(a.id, b.id, "sibling")
        members.extend(kids)
        gp_p = fam["grandparent_prob"].get(g, fam["grandparent_prob"]["default"])
        if rng.random() < gp_p:
            gp_age = float(np.clip(age1 + rng.uniform(22, 35), *fam["grandparent_age"].values()))
            gp = self.make_person(hh, "female" if rng.random() < 0.65 else "male", gp_age, "grandparent",
                                  family=family)  # fmt: skip
            self.link(head.id, gp.id, "mother" if gp.sex == "female" else "father")
            for k in kids:
                self.link(k.id, gp.id, "grandparent")
            members.append(gp)
        return members

    def extended_links(self) -> None:
        """Aunt/uncle and cousin links derived from adult sibling pairs across households."""
        kids_of: dict[str, list[str]] = {}
        for r in self.c.relationships:
            if r.type == "child":
                kids_of.setdefault(r.person_id, []).append(r.related_person_id)
        pairs = [(r.person_id, r.related_person_id) for r in self.c.relationships if r.type == "sibling"]
        existing = {(r.person_id, r.related_person_id) for r in self.c.relationships}
        for a, b in pairs:
            pa, pb = self.by_id[a], self.by_id[b]
            if pa.household_id == pb.household_id or a > b:
                continue
            for k in kids_of.get(a, []):
                if (k, b) not in existing:
                    self.link(k, b, "aunt_uncle")
                    existing.add((k, b))
            for k in kids_of.get(b, []):
                if (k, a) not in existing:
                    self.link(k, a, "aunt_uncle")
                    existing.add((k, a))
            for ka in kids_of.get(a, []):
                for kb in kids_of.get(b, []):
                    if (ka, kb) not in existing:
                        self.link(ka, kb, "cousin")
                        existing.add((ka, kb))

    def build(self, n_target: int) -> None:
        rng, p = self.rng, self.p
        hp = p["households"]
        labour_share = hp["labour_share_of_people"]
        # Household-level probability of a labour unit so that ~labour_share of PEOPLE live in one.
        mean_labour = (hp["labour_size"]["min"] + hp["labour_size"]["max"]) / 2
        p_labour_hh = (labour_share / mean_labour) / (labour_share / mean_labour + (1 - labour_share) / 3.8)
        # Family nationality weights, adjusted for the labour population's nationality mix.
        mix = dict(p["nationality_mix"])
        fam_w = {k: max(1e-4, v - labour_share * hp["labour_nationality"].get(k, 0)) for k, v in mix.items()}
        heads: list[Person] = []
        sib_p = p["siblings"]["adult_sibling_target"] * 0.75
        while len(self.c.people) < n_target:
            if rng.random() < p_labour_hh:
                self.labour_household()
                continue
            g = choice(rng, fam_w)
            same_g = [h for h in heads[-400:] if h.nationality_group == g]
            sib = same_g[int(rng.integers(len(same_g)))] if same_g and rng.random() < sib_p else None
            members = self.family_household(g, sibling_of=sib)
            heads.append(members[0])
        self.extended_links()
