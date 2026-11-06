"""Pydantic schema for guideline rule YAML files (content/rules/*.yaml)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from wiqaya.common.paths import RULES_DIR

Pathway = Literal["wcv", "immunisation", "developmental", "adult_screening", "followup", "cascade"]
Kind = Literal["periodic", "schedule", "immunisation", "followup", "cascade"]
RuleStatus = Literal["demo_encoding_requires_clinical_validation", "unverified_source"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Range(_Strict):
    min: float | None = None
    max: float | None = None

    def contains(self, x: float) -> bool:
        return (self.min is None or x >= self.min) and (self.max is None or x <= self.max)


class Source(_Strict):
    name: str
    year: int
    url: str
    retrieved_on: str | None = None
    licence: str
    verified: bool = False
    http_status: int | None = None
    verification_url: str | None = None  # e.g. archive or PubMed copy when the publisher blocks bots
    key_facts: tuple[str, ...] = ()


class Criterion(_Strict):
    """One eligibility criterion. All given fields must hold (AND)."""

    bmi_min: float | None = None
    conditions_any: tuple[str, ...] = ()
    family_history_any: tuple[str, ...] = ()


class AppliesTo(_Strict):
    age_years: Range | None = None
    sex: Literal["female", "male"] | None = None
    any_of: tuple[Criterion, ...] = ()
    exclude_conditions: tuple[str, ...] = ()


class EligibleEarly(_Strict):
    reason: str
    when: Criterion
    age_years: Range


class IntervalOverride(_Strict):
    """Use a shorter interval when the last result of `obs` falls in a range."""

    obs: str
    range: Range
    interval_months: int
    reason: str


class IntervalByAge(_Strict):
    age_years: Range
    interval_months: int


class Trigger(_Strict):
    """Follow-up trigger: the latest result of any listed observation is in range."""

    any_of: tuple[dict[str, float | str], ...]
    lookback_months: int = 36


class Cascade(_Strict):
    index_genes: tuple[str, ...] = ()
    index_conditions: tuple[str, ...] = ()
    relationships: tuple[Literal["parent", "child", "sibling"], ...] = ("parent", "child", "sibling")
    child_min_age_years: float = 0
    relative_min_age_years: float = 0
    outreach_allowed_after_approval: bool = True


class Rule(_Strict):
    id: str
    version: str
    title: str
    pathway: Pathway
    kind: Kind
    status: RuleStatus
    source: Source
    message_pathway: str | None = None
    slot_type: Literal["child", "adult", "women"]
    requires_clinician: bool = False
    applies_to: AppliesTo = Field(default_factory=AppliesTo)
    interval_months: int | None = None
    interval_by_age: tuple[IntervalByAge, ...] = ()
    interval_by_test: dict[str, int] = Field(default_factory=dict)
    interval_overrides: tuple[IntervalOverride, ...] = ()
    eligible_early: tuple[EligibleEarly, ...] = ()
    schedule_ref: str | None = None
    trigger: Trigger | None = None
    followup_window_months: int | None = None
    cascade: Cascade | None = None
    data_required: tuple[str, ...]
    satisfied_by: tuple[str, ...] = ()
    output_codes: dict[str, str]
    assumptions: tuple[str, ...] = ()

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"

    @model_validator(mode="after")
    def _check_kind(self) -> Rule:
        need = {
            "periodic": ["satisfied_by"],
            "schedule": ["schedule_ref", "satisfied_by"],
            "followup": ["trigger", "followup_window_months", "satisfied_by"],
            "cascade": ["cascade"],
            "immunisation": ["schedule_ref"],
        }[self.kind]
        for f in need:
            if not getattr(self, f):
                raise ValueError(f"{self.id}: kind={self.kind} requires '{f}'")
        if self.kind == "periodic" and not (self.interval_months or self.interval_by_age or self.interval_by_test):
            raise ValueError(f"{self.id}: periodic rule needs an interval")
        if self.kind == "cascade" and not self.requires_clinician:
            raise ValueError(f"{self.id}: cascade rules must require a clinician")
        return self


def load_rule(path: Path) -> Rule:
    with path.open(encoding="utf-8") as fh:
        return Rule.model_validate(yaml.safe_load(fh))


@lru_cache(maxsize=4)
def load_rules(base: Path = RULES_DIR) -> tuple[Rule, ...]:
    return tuple(load_rule(p) for p in sorted(base.glob("*.yaml")))
