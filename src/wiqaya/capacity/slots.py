"""Slot supply for the 12-week evaluation period (config/capacity.yaml)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pandas as pd

from wiqaya.common import calendar as cal
from wiqaya.common import config as C


@dataclass(frozen=True)
class Site:
    id: str
    kind: str  # clinic | van
    district_id: str
    lat: float
    lon: float
    weekday: str | None = None  # van stop day
    open_time: str = "08:00"
    close_time: str = "20:00"


def sites() -> dict[str, Site]:
    out: dict[str, Site] = {}
    for c in C.clinics().values():
        o = c.get("opening", {})
        out[c["id"]] = Site(c["id"], "clinic", c["district_id"], c["lat"], c["lon"], None,
                            o.get("open", "08:00"), o.get("close", "20:00"))  # fmt: skip
    for s in C.van_stops().values():
        out[s["id"]] = Site(s["id"], "van", s["district_id"], s["lat"], s["lon"], s["weekday"], s["open"], s["close"])
    return out


def weeks(start: date, n: int) -> list[tuple[int, date]]:
    return [(i, start + timedelta(days=7 * i)) for i in range(n)]


def open_days(site: Site, week_start: date) -> list[date]:
    days = [week_start + timedelta(days=i) for i in range(7)]
    if site.kind == "van":
        return [d for d in days if cal.weekday(d) == site.weekday and cal.closure_reason(d) is None]
    return [d for d in days if cal.clinic_open(d)]


def build_capacity(n_open_gaps: int, people: pd.DataFrame, start: date, n_weeks: int) -> pd.DataFrame:
    """Buckets (site, week, slot_type) with capacity. Clinic slots scale with the people assigned to each clinic."""
    cap = C.cfg("capacity")
    total = int(round(cap["target_share_of_open_gaps"] * n_open_gaps))
    st_w = cap["slot_type_weights"]
    assigned = people.groupby("assigned_clinic_id").size()
    all_sites = sites()
    clinic_ids = sorted(s.id for s in all_sites.values() if s.kind == "clinic")
    weights = {cid: float(assigned.get(cid, 0)) + 50.0 for cid in clinic_ids}  # floor so small clinics keep slots
    wsum = sum(weights.values())
    rows: list[dict[str, Any]] = []
    total_open_days = {
        cid: sum(len(open_days(all_sites[cid], ws)) for _, ws in weeks(start, n_weeks)) for cid in clinic_ids
    }
    for cid in clinic_ids:
        site_total = total * weights[cid] / wsum
        for w, ws in weeks(start, n_weeks):
            nd = len(open_days(all_sites[cid], ws))
            if not nd or not total_open_days[cid]:
                continue
            week_total = site_total * nd / total_open_days[cid]
            for st, sw in st_w.items():
                rows.append({"site_id": cid, "kind": "clinic", "week": w, "week_start": ws, "slot_type": st,
                             "capacity": int(round(week_total * sw))})  # fmt: skip
    van = cap["mobile_van"]
    for s in sorted((x for x in all_sites.values() if x.kind == "van"), key=lambda x: x.id):
        for w, ws in weeks(start, n_weeks):
            if open_days(s, ws):
                rows.append({"site_id": s.id, "kind": "van", "week": w, "week_start": ws, "slot_type": van["slot_type"],
                             "capacity": int(van["slots_per_stop"])})  # fmt: skip
    df = pd.DataFrame(rows)
    return df[df.capacity > 0].reset_index(drop=True)
