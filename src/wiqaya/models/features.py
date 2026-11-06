"""Feature builders for Model R (risk elevation) and Model N (no-show).

Monitoring segments (nationality, language, district id, insurance tier) are NEVER Model R features.
`FORBIDDEN_R` is asserted in code and in tests.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from wiqaya.common import config as C
from wiqaya.common.geo import haversine_km

# Model R declares exactly which fields it reads (privacy by construction).
DATA_REQUIRED_R = ("birth_date", "sex", "obs:bmi", "obs:hba1c", "obs:sbp", "obs:dbp", "obs:ldl", "conditions",
                   "family_history", "genomic[consented]", "appointments:noshow", "district_deprivation_proxy",
                   "encounters")  # fmt: skip
FEATURES_R = ["age", "sex_female", "bmi_last", "bmi_trend", "hba1c_last", "hba1c_trend", "sbp_last", "dbp_last",
              "ldl_last", "n_conditions", "fhx_t2d", "fhx_cvd", "fhx_crc", "fhx_breast", "genomic_flag",
              "missed_visits", "deprivation", "months_since_screen", "encounters_24m"]  # fmt: skip
FORBIDDEN_R = {"nationality_group", "preferred_language", "language", "district_id", "insurance_tier"}
DATA_REQUIRED_N = ("past_invitations", "past_attendance", "distance_to_clinic", "phone_type", "channel",
                   "message_language", "preferred_language[match only]", "household_size", "housing_type")  # fmt: skip
FEATURES_N = ["past_attendance_rate", "past_invites", "distance_km", "phone_basic", "phone_none", "ch_whatsapp",
              "ch_sms", "ch_call", "ch_chw", "language_match", "household_size", "labour_accommodation"]  # fmt: skip
SCREEN_TYPES = {"adult_screen", "mobile_van"}
DETECTABLE = {"t2d", "prediabetes", "hypertension", "dyslipidaemia", "fh", "cin2plus", "colorectal_neoplasia"}

assert not set(FEATURES_R) & FORBIDDEN_R


def _slope(series: list[tuple[date, float]]) -> float:
    if len(series) < 2:
        return float("nan")
    x = np.array([(d - series[0][0]).days / 365.25 for d, _ in series])
    y = np.array([v for _, v in series])
    if np.ptp(x) < 0.1:
        return float("nan")
    return float(np.polyfit(x, y, 1)[0])


def risk_features(t: dict[str, pd.DataFrame], ref: date, people: pd.DataFrame | None = None) -> pd.DataFrame:
    """Model R features for every adult as of `ref`, using only data dated before `ref`."""
    people = t["people"] if people is None else people
    dep = C.cfg("population")["district_deprivation_proxy"]
    consent = t["consents"]
    genomic_ok = set(consent[(consent.category == "genomic") & (consent.status == "granted")].person_id)
    gen_people = set(t["genomic"][t["genomic"].date < ref].person_id) & genomic_ok
    obs = t["observations"][t["observations"].date < ref]
    obs_by: dict[tuple[str, str], list[tuple[date, float]]] = {}
    for r in obs.sort_values(["person_id", "key", "date"], kind="mergesort").itertuples(index=False):
        obs_by.setdefault((r.person_id, r.key), []).append((r.date, float(r.value)))
    cond = t["conditions"][(t["conditions"].onset_date < ref) & (t["conditions"].verification == "confirmed")]
    n_cond = cond.groupby("person_id").size().to_dict()
    fh = t["family_history"].groupby("person_id")["condition_key"].apply(set).to_dict()
    enc = t["encounters"][t["encounters"].date < ref]
    missed = enc[~enc.attended].groupby("person_id").size().to_dict()
    att = enc[enc.attended]
    recent = att[att.date >= ref - timedelta(days=730)].groupby("person_id").size().to_dict()
    last_screen = att[att.type.isin(SCREEN_TYPES)].groupby("person_id")["date"].max().to_dict()
    rows = []
    for p in people.itertuples(index=False):
        age = (ref - p.birth_date).days / 365.25
        if age < 18:
            continue
        pid = p.id

        def last(key: str, _pid: str = pid) -> float:
            s = obs_by.get((_pid, key))
            return s[-1][1] if s else np.nan

        f = fh.get(pid, set())
        ls = last_screen.get(pid)
        rows.append({
            "person_id": pid, "age": age, "sex_female": int(p.sex == "female"),
            "bmi_last": last("bmi"), "bmi_trend": _slope(obs_by.get((pid, "bmi"), [])),
            "hba1c_last": last("hba1c"), "hba1c_trend": _slope(obs_by.get((pid, "hba1c"), [])),
            "sbp_last": last("sbp"), "dbp_last": last("dbp"), "ldl_last": last("ldl"),
            "n_conditions": n_cond.get(pid, 0), "fhx_t2d": int("t2d" in f), "fhx_cvd": int("premature_cvd" in f),
            "fhx_crc": int("colorectal" in f), "fhx_breast": int("breast" in f),
            "genomic_flag": int(pid in gen_people), "missed_visits": missed.get(pid, 0),
            "deprivation": dep.get(p.district_id, 0.5),
            "months_since_screen": (ref - ls).days / 30.4375 if ls else 120.0,
            "encounters_24m": recent.get(pid, 0),
        })  # fmt: skip
    df = pd.DataFrame(rows)
    assert not set(df.columns) & FORBIDDEN_R
    return df


def risk_labels(t: dict[str, pd.DataFrame], ref: date, end: date) -> pd.DataFrame:
    """Observed outcome only: a condition detected in [ref, end) among adults screened in that window."""
    enc = t["encounters"]
    screened = set(enc[enc.attended & enc.type.isin(SCREEN_TYPES) & (enc.date >= ref) & (enc.date < end)].person_id)
    cond = t["conditions"]
    new = cond[(cond.onset_date >= ref) & (cond.onset_date < end) & cond.key.isin(DETECTABLE)]
    pos = set(new.person_id)
    return pd.DataFrame({"person_id": sorted(screened), "label": [int(p in pos) for p in sorted(screened)]})


def _distance(p: Any, clinics: dict[str, dict[str, Any]]) -> float:
    c = clinics[p.assigned_clinic_id]
    return haversine_km(p.lat, p.lon, c["lat"], c["lon"])


def noshow_training(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per past invitation; label = 1 if no attended visit followed within 30 days."""
    clinics = C.clinics()
    people = t["people"].set_index("id")
    comms = t["communications"].sort_values(["person_id", "sent_at"], kind="mergesort")
    enc = t["encounters"]
    att = enc[enc.attended & enc.type.isin(SCREEN_TYPES)]
    att_dates = att.groupby("person_id")["date"].apply(sorted).to_dict()
    hh_size = t["people"].groupby("household_id").size().to_dict()
    rows = []
    history: dict[str, list[int]] = {}
    for r in comms.itertuples(index=False):
        p = people.loc[r.person_id]
        attended = any(r.sent_at <= d <= r.sent_at + timedelta(days=30) for d in att_dates.get(r.person_id, []))
        past = history.setdefault(r.person_id, [])
        rows.append(_n_row(r.person_id, p, r.channel, r.language, len(past),
                           (sum(past) / len(past)) if past else 0.5, _distance(p, clinics), hh_size)
                    | {"label": int(not attended)})  # fmt: skip
        past.append(int(attended))
    return pd.DataFrame(rows)


def _n_row(pid: str, p: Any, channel: str, language: str, n_past: int, rate: float, dist: float,
           hh_size: dict[str, int]) -> dict[str, Any]:  # fmt: skip
    return {
        "person_id": pid, "past_attendance_rate": rate, "past_invites": n_past, "distance_km": dist,
        "phone_basic": int(p.phone_type == "basic"), "phone_none": int(p.phone_type == "none"),
        "ch_whatsapp": int(channel == "whatsapp"), "ch_sms": int(channel == "sms"),
        "ch_call": int(channel == "call_script"), "ch_chw": int(channel == "chw_script"),
        "language_match": int(language == p.preferred_language), "household_size": hh_size.get(p.household_id, 1),
        "labour_accommodation": int(p.housing_type == "labour_accommodation"),
    }  # fmt: skip


def noshow_scoring(t: dict[str, pd.DataFrame], plan: dict[str, tuple[str, str]],
                   site_distance: dict[str, float] | None = None) -> pd.DataFrame:  # fmt: skip
    """Model N features for the planned contact (channel, language) per person at T0."""
    clinics = C.clinics()
    people = t["people"].set_index("id")
    comms = t["communications"]
    enc = t["encounters"]
    att = enc[enc.attended & enc.type.isin(SCREEN_TYPES)]
    att_dates = att.groupby("person_id")["date"].apply(list).to_dict()
    n_inv = comms.groupby("person_id").size().to_dict()
    hh_size = t["people"].groupby("household_id").size().to_dict()
    resp: dict[str, list[int]] = {}
    for r in comms.itertuples(index=False):
        resp.setdefault(r.person_id, []).append(
            int(any(r.sent_at <= d <= r.sent_at + timedelta(days=30) for d in att_dates.get(r.person_id, [])))
        )
    rows = []
    for pid, (channel, language) in plan.items():
        p = people.loc[pid]
        past = resp.get(pid, [])
        dist = site_distance[pid] if site_distance and pid in site_distance else _distance(p, clinics)
        rows.append(_n_row(pid, p, channel, language, n_inv.get(pid, 0), (sum(past) / len(past)) if past else 0.5,
                           dist, hh_size))  # fmt: skip
    return pd.DataFrame(rows)
