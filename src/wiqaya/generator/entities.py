"""Canonical synthetic entities (PROMPT.md §3.1). All records are synthetic."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class Household:
    id: str
    district_id: str
    housing_type: str  # villa | apartment | labour_accommodation
    primary_language: str
    nationality_group: str
    lat: float
    lon: float
    size: int = 0


@dataclass
class Person:
    id: str
    household_id: str
    given: str
    family: str
    sex: str  # female | male
    birth_date: date
    nationality_group: str
    preferred_language: str
    literacy_proxy: str  # low | med | high
    phone_type: str  # smartphone | basic | none
    insurance_tier: str  # Thiqa | Enhanced | Basic
    district_id: str
    has_regular_clinic: bool
    assigned_clinic_id: str
    role: str  # head | spouse | child | grandparent | worker | adult
    lat: float
    lon: float
    pinned: bool = False  # demo persona: history is fixed, not random


@dataclass
class Relationship:
    person_id: str
    related_person_id: str
    type: str  # related person is <type> of person: mother|father|child|sibling|spouse|grandparent|...
    degree: int


@dataclass
class Encounter:
    id: str
    person_id: str
    date: date
    type: str  # wcv | adult_screen | acute | chronic_review | mobile_van
    clinic_id: str
    attended: bool
    scheduled_via: str  # walk_in | invite_baseline | invite_wiqaya | self


@dataclass
class Observation:
    id: str
    person_id: str
    date: date
    key: str
    value: float
    encounter_id: str | None = None


@dataclass
class Condition:
    id: str
    person_id: str
    key: str
    onset_date: date
    verification: str  # confirmed | suspected


@dataclass
class Immunization:
    id: str
    person_id: str
    vaccine: str
    date: date


@dataclass
class FamilyHistory:
    id: str
    person_id: str
    relative_type: str
    condition_key: str
    onset_age: int | None = None


@dataclass
class GenomicFinding:
    id: str
    person_id: str
    gene: str
    variant_ref: str | None
    variant_name: str
    classification: str  # pathogenic | likely_pathogenic
    date: date
    source: str = "genome_programme_sim"


@dataclass
class Consent:
    id: str
    person_id: str
    category: str
    status: str  # granted | denied | not_asked
    date: date


@dataclass
class ContactPreference:
    person_id: str
    channel_order: list[str]
    quiet_hours: str = "21:00-08:00"
    pathway_opt_outs: list[str] = field(default_factory=list)
    remind_later_until: date | None = None


@dataclass
class Communication:
    id: str
    person_id: str
    household_id: str
    template_id: str
    language: str
    channel: str
    sent_at: date
    response: str  # booked | declined | later | none
    policy: str  # baseline | random | wiqaya
    pathway: str
    simulated: bool = True


@dataclass
class Cohort:
    households: list[Household] = field(default_factory=list)
    people: list[Person] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    encounters: list[Encounter] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    conditions: list[Condition] = field(default_factory=list)
    immunizations: list[Immunization] = field(default_factory=list)
    family_history: list[FamilyHistory] = field(default_factory=list)
    genomic: list[GenomicFinding] = field(default_factory=list)
    consents: list[Consent] = field(default_factory=list)
    preferences: list[ContactPreference] = field(default_factory=list)
    communications: list[Communication] = field(default_factory=list)
    latent: dict[str, dict[str, Any]] = field(default_factory=dict)  # HIDDEN ground truth
