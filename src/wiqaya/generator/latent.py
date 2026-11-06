"""Latent ground truth (PROMPT.md §4 steps 4 and 6).

The latent table is HIDDEN: only the generator and the evaluator read it. Models and the API never do.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

import numpy as np

from wiqaya.common import config as C
from wiqaya.generator.entities import Cohort, Condition, FamilyHistory, GenomicFinding, Person

CHANNELS = ("whatsapp", "sms", "call_script", "chw_script")


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def age_on(p: Person, d: date) -> float:
    return (d - p.birth_date).days / 365.25


class LatentBuilder:
    def __init__(self, cohort: Cohort, rng: np.random.Generator, t0: date) -> None:
        self.c, self.rng, self.t0 = cohort, rng, t0
        self.p = C.cfg("population")
        self.by_id = {x.id: x for x in cohort.people}
        self.parents: dict[str, list[str]] = {}
        self.siblings: dict[str, list[str]] = {}
        self.spouse: dict[str, str] = {}
        for r in cohort.relationships:
            if r.type in ("mother", "father"):
                self.parents.setdefault(r.person_id, []).append(r.related_person_id)
            elif r.type == "sibling":
                self.siblings.setdefault(r.person_id, []).append(r.related_person_id)
            elif r.type == "spouse":
                self.spouse[r.person_id] = r.related_person_id
        self.n_cond = 0
        self.n_fhx = 0
        self.n_gen = 0

    # ----------------------------------------------------------------- inheritance
    def _inherited(self, founder_p: dict[str, float], key: str) -> dict[str, bool]:
        """Autosomal inheritance over the in-cohort pedigree.

        Founders (no parent in the cohort) carry with founder_p. Adult sibling groups without an in-cohort
        parent share a virtual parent who carries with 2*p. Children inherit with p=0.5 from each carrier parent.
        """
        rng = self.rng
        status: dict[str, bool] = {}
        people = sorted(self.c.people, key=lambda x: x.birth_date)  # parents before children
        group_parent: dict[str, bool] = {}
        for person in people:
            if person.id in status:
                continue
            fp = founder_p.get(person.nationality_group, founder_p["default"])
            pars = [q for q in self.parents.get(person.id, []) if q in status]
            if pars:
                p_carry = 1 - math.prod(0.5 if status[q] else 1.0 for q in pars)
                # A parent not in the cohort can still pass it on.
                if len(pars) == 1:
                    p_carry = 1 - (1 - p_carry) * (1 - fp)
                status[person.id] = bool(rng.random() < p_carry)
                continue
            sibs = self.siblings.get(person.id, [])
            if sibs:
                gid = min([person.id, *sibs])
                if gid not in group_parent:
                    group_parent[gid] = bool(rng.random() < min(1.0, 2 * fp))
                status[person.id] = bool(rng.random() < (0.5 if group_parent[gid] else fp))
            else:
                status[person.id] = bool(rng.random() < fp)
        return status

    # ----------------------------------------------------------------- main
    def build(self) -> None:
        rng, p, t0 = self.rng, self.p, self.t0
        fh_cfg = p["fh"]
        cons = p["consanguinity_share_emirati"]
        fh_founder = {
            "emirati": fh_cfg["founder_prevalence"] * (1 + (fh_cfg["consanguinity_founder_multiplier"] - 1) * cons),
            "default": fh_cfg["founder_prevalence"],
        }
        fh = self._inherited(fh_founder, "fh")
        hbb = self._inherited({"default": p["hbb_carrier_prob"]}, "hbb")
        # Consanguinity: a carrier's consanguineous spouse is more likely to carry (recessive co-occurrence).
        consang: set[str] = set()
        for a, b in self.spouse.items():
            pa = self.by_id[a]
            if pa.nationality_group == "emirati" and a < b:
                if rng.random() < cons:
                    consang.update({a, b})
                    if hbb[a] and not hbb[b] and rng.random() < p["hbb_carrier_prob_if_consanguineous_spouse_carrier"]:
                        hbb[b] = True
        brca = self._inherited({"default": p["brca_prob"]}, "brca")
        models = p["latent_models"]
        bcfg = p["bmi"]
        rm = C.cfg("simulation")["response_model"]
        for person in self.c.people:
            age = age_on(person, t0)
            g = person.nationality_group
            lt: dict[str, Any] = {
                "fh_carrier": fh[person.id],
                "hbb_carrier": hbb[person.id],
                "brca_carrier": brca[person.id],
                "consanguineous_marriage": person.id in consang,
            }
            # Family history flags (recorded history, not the truth of relatives).
            fhx_t2d = rng.random() < 0.25 + (0.1 if g in ("emirati", "indian", "pakistani") else 0)
            fhx_cvd = rng.random() < (0.5 if fh[person.id] else 0.07)
            fhx_crc = rng.random() < 0.05
            fhx_breast = rng.random() < (0.5 if brca[person.id] else 0.05)
            lt["family_history"] = {"t2d": fhx_t2d, "premature_cvd": fhx_cvd, "colorectal": fhx_crc,
                                    "breast": fhx_breast}  # fmt: skip
            if age >= 18:
                bmi = float(np.clip(rng.normal(bcfg["adult"]["mean"] + bcfg["adult"]["age_slope"] * (age - 30)
                                               + bcfg["group_shift"].get(g, 0), bcfg["adult"]["sd"]),
                                    bcfg["adult"]["min"], bcfg["adult"]["max"]))  # fmt: skip
                if person.role == "worker":
                    bmi -= 1.0
                lt["bmi"] = round(bmi, 1)

                def logit(m: dict[str, Any], fhx: bool, _age: float = age, _bmi: float = bmi) -> float:
                    return float(m["intercept"] + m["age"] * (_age - 40) + m["bmi"] * (_bmi - 25)
                                 + m["fhx"] * fhx + m["group"].get(g, 0))  # fmt: skip

                t2d = rng.random() < _sigmoid(logit(models["t2d"], fhx_t2d))
                pre = (not t2d) and rng.random() < _sigmoid(logit(models["prediabetes"], fhx_t2d))
                htn = rng.random() < _sigmoid(logit(models["hypertension"], fhx_cvd))
                dys = fh[person.id] or rng.random() < _sigmoid(logit(models["dyslipidaemia"], fhx_cvd))
                lt.update(undiagnosed_t2d=t2d, prediabetes=pre, hypertension=htn, dyslipidaemia=dys)
                lt["cervical_cin2plus"] = bool(person.sex == "female" and 21 <= age <= 65
                                               and rng.random() < models["cervical_cin2plus"]["rate"])  # fmt: skip
                lt["colorectal_advanced_neoplasia"] = bool(
                    age >= 45 and rng.random() < _sigmoid(logit(models["colorectal_advanced_neoplasia"], fhx_crc))
                )
                lt["developmental_delay"] = False
                lt["child_high_bmi"] = False
            else:
                lt.update(undiagnosed_t2d=False, prediabetes=False, hypertension=False,
                          dyslipidaemia=bool(fh[person.id]), cervical_cin2plus=False,
                          colorectal_advanced_neoplasia=False)  # fmt: skip
                lt["developmental_delay"] = bool(age < 6 and rng.random() < models["developmental_delay"]["rate"])
                lt["child_high_bmi"] = bool(age >= 2 and rng.random() < bcfg["child_obesity_prob"])
                lt["bmi"] = None
            # Response behaviour (used ONLY by the simulator's response model).
            base = float(rng.normal(0, rm["person_effect_sd"]))
            if person.role == "worker":
                base -= 0.3
            lt["response_propensity_by_channel"] = {ch: round(base + float(rng.normal(0, 0.3)), 4) for ch in CHANNELS}
            lt["language_sensitivity"] = round(float(rng.lognormal(0, 0.25)), 4)
            lt["distance_sensitivity"] = round(float(rng.lognormal(0, 0.25)), 4)
            lt["bundle_effect"] = round(float(rng.lognormal(0, 0.25)), 4)
            self.c.latent[person.id] = lt
        self._family_history_records()
        self._diagnosed_before_history()
        self._genomics()

    # ----------------------------------------------------------------- records
    def _family_history_records(self) -> None:
        rel = {"t2d": "parent", "premature_cvd": "parent", "colorectal": "parent", "breast": "mother"}
        for person in self.c.people:
            if person.pinned:
                continue
            for key, flag in self.c.latent[person.id]["family_history"].items():
                if flag:
                    self.n_fhx += 1
                    self.c.family_history.append(
                        FamilyHistory(
                            f"fhx-{self.n_fhx:07d}", person.id, rel[key], key, int(self.rng.integers(40, 70))
                        )  # fmt: skip
                    )

    def _cond(self, pid: str, key: str, onset: date, verification: str = "confirmed") -> None:
        self.n_cond += 1
        self.c.conditions.append(Condition(f"cond-pre-{self.n_cond:07d}", pid, key, onset, verification))

    def _diagnosed_before_history(self) -> None:
        share = self.p["diagnosed_before_history"]
        history_start = self.t0 - timedelta(days=int(self.p["history_months"] * 30.4375))
        for person in self.c.people:
            if person.pinned:
                continue
            lt = self.c.latent[person.id]
            for key, lkey in (("t2d", "undiagnosed_t2d"), ("hypertension", "hypertension"),
                              ("dyslipidaemia", "dyslipidaemia"), ("prediabetes", "prediabetes")):  # fmt: skip
                if lt.get(lkey) and self.rng.random() < share[key]:
                    onset = history_start - timedelta(days=int(self.rng.integers(30, 3000)))
                    if onset > person.birth_date + timedelta(days=18 * 365):
                        self._cond(person.id, key, onset)
                        lt[lkey] = False  # diagnosed -> no longer latent/undiagnosed
                        lt[f"{key}_diagnosed"] = True
            if lt["fh_carrier"] and self.rng.random() < self.p["fh"]["diagnosed_share"]:
                if age_on(person, self.t0) >= 10:
                    self._cond(person.id, "fh", history_start - timedelta(days=int(self.rng.integers(30, 2000))))
                    lt["fh_diagnosed"] = True

    def _genomics(self) -> None:
        cache = C.reference("clinvar_cache.json")["genes"]
        part = self.p["genome_programme"]["participation"]
        for person in self.c.people:
            if person.pinned:
                continue
            lt = self.c.latent[person.id]
            pp = part.get(person.nationality_group, part["default"])
            if self.rng.random() >= pp:
                continue
            lt["genome_programme"] = True
            genes: list[str] = []
            if lt["fh_carrier"]:
                genes.append(str(self.rng.choice(["LDLR", "APOB", "PCSK9"], p=[0.75, 0.15, 0.10])))
            if lt["hbb_carrier"]:
                genes.append("HBB")
            if lt["brca_carrier"]:
                genes.append(str(self.rng.choice(["BRCA1", "BRCA2"])))
            for gene in genes:
                variants = cache.get(gene) or [{"variation_id": None, "name": "illustrative variant"}]
                v = variants[int(self.rng.integers(len(variants)))]
                self.n_gen += 1
                self.c.genomic.append(GenomicFinding(
                    id=f"gen-{self.n_gen:06d}", person_id=person.id, gene=gene,
                    variant_ref=v.get("variation_id"), variant_name=v.get("name", "illustrative variant"),
                    classification="pathogenic" if self.rng.random() < 0.8 else "likely_pathogenic",
                    date=self.t0 - timedelta(days=int(self.rng.integers(60, 1000))),
                ))  # fmt: skip
