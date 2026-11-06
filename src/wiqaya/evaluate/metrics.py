"""Evaluation metrics per policy, overall and per segment (PROMPT.md §7).

Only this package and the simulator may read latent ground truth (for FN rates and yield).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from wiqaya.common import config as C
from wiqaya.governance.suppress import suppress_records

SEGMENTS = {"nationality_group": "nationality_group", "language": "preferred_language", "age_band": "age_band",
            "sex": "sex", "district": "district_id", "housing_type": "housing_type",
            "insurance_tier": "insurance_tier", "district_x_nationality": "district_x_nationality"}  # fmt: skip


def with_age_band(people: pd.DataFrame, as_of: date) -> pd.DataFrame:
    cfg = C.cfg("segments")["segments"]["age_band"]
    p = people.copy()
    age = p.birth_date.map(lambda b: (as_of - b).days / 365.25)
    p["age_band"] = pd.cut(age, bins=cfg["bins"], labels=cfg["labels"], right=False).astype(str)
    # A deliberately fine-grained segment: small cells show the n<11 suppression rule in action.
    p["district_x_nationality"] = p.district_id + " / " + p.nationality_group
    return p


def policy_metrics(res: dict[str, Any], gaps: pd.DataFrame, latent: dict[str, dict[str, Any]], start: date,
                   n_slots: int, n_flags: int) -> dict[str, Any]:  # fmt: skip
    from wiqaya.simulate.engine import RULE_LATENT

    items = res["items"]
    comms, enc = res["comms"], res["encounters"]
    people_with_gaps = gaps.person_id.nunique()
    done = [i for i in items if i.done]
    closed_gap_ids = {g for i in done for g in i.gap_ids}
    contacts = len(comms)
    contacted = comms.person_id.nunique() if contacts else 0
    fu = gaps[gaps.pathway == "followup"]
    hp_done = [i for i in done if i.high_priority]
    # FN: people with an undetected latent condition linked to one of their open gaps, not reached.
    rules_by_person = gaps.groupby("person_id").rule_id.apply(set).to_dict()
    latent_pos = [pid for pid, rules in rules_by_person.items()
                  if any(latent.get(pid, {}).get(k) for r in rules for k, _, _ in RULE_LATENT.get(r, []))]  # fmt: skip
    reached = {i.person_id for i in done}
    det_counts: dict[str, int] = {}
    for i in done:
        for d in i.detections:
            det_counts[d] = det_counts.get(d, 0) + 1
    days = [(i.attended_on - start).days for i in done if i.attended_on]
    declined = sum(1 for i in items if i.declined)
    review = res.get("review", {})
    return {
        "people_with_gaps": int(people_with_gaps),
        "targeted_people": len(items),
        "contacts": int(contacts),
        "people_contacted": int(contacted),
        "reach_pct": round(100 * contacted / people_with_gaps, 2) if people_with_gaps else None,
        "completed_visits": len(done),
        "completed_per_100_contacts": round(100 * len(done) / contacts, 2) if contacts else None,
        "gaps_closed_pct": round(100 * len(closed_gap_ids) / len(gaps), 2) if len(gaps) else None,
        "median_days_to_attendance": float(np.median(days)) if days else None,
        "followup_completion_pct": round(100 * fu.id.isin(closed_gap_ids).mean(), 2) if len(fu) else None,
        "false_positive_rate_pct": round(100 * sum(1 for i in hp_done if not i.detections) / len(hp_done), 2) if hp_done else None,
        "false_negative_rate_pct": round(100 * sum(1 for p in latent_pos if p not in reached) / len(latent_pos), 2) if latent_pos else None,
        "latent_positive_people": len(latent_pos),
        "detections": det_counts,
        "yield_per_1000_screened": {k: round(1000 * v / len(done), 2) for k, v in det_counts.items()} if done else {},
        "screen_false_positive_referrals": sum(1 for i in done if i.false_positive),
        "decline_optout_pct": round(100 * declined / contacted, 2) if contacted else None,
        "reviewer_override_pct": round(100 * review.get("rejected", 0) / review["reviewed"], 2) if review.get("reviewed") else None,
        "flags_per_slot": round(n_flags / n_slots, 2) if n_slots else None,
        "bundled_messages": int(comms.bundled.sum()) if contacts else 0,
        "van_visits": int(enc.site_kind.eq("van").sum()) if len(enc) else 0,
        "chw_contacts": int(comms.channel.eq("chw_script").sum()) if contacts else 0,
    }  # fmt: skip


def segment_metrics(res: dict[str, Any], gaps: pd.DataFrame, people: pd.DataFrame, as_of: date) -> dict[str, Any]:
    p = with_age_band(people, as_of).set_index("id")
    items = {i.person_id: i for i in res["items"]}
    comms = res["comms"]
    contacts_by = comms.groupby("person_id").size().to_dict() if len(comms) else {}
    g = gaps.copy()
    g["closed"] = [items.get(pid) is not None and items[pid].done and gid in items[pid].gap_ids
                   for pid, gid in zip(g.person_id, g.id, strict=True)]  # fmt: skip
    persons = pd.DataFrame({"person_id": sorted(g.person_id.unique())})
    persons["contacted"] = persons.person_id.map(lambda x: contacts_by.get(x, 0) > 0)
    persons["contacts"] = persons.person_id.map(lambda x: contacts_by.get(x, 0))
    persons["done"] = persons.person_id.map(lambda x: bool(items.get(x) and items[x].done))
    min_n = C.cfg("segments")["min_cell_n"]
    out: dict[str, Any] = {}
    for seg, col in SEGMENTS.items():
        persons[seg] = persons.person_id.map(p[col])
        g[seg] = g.person_id.map(p[col])
        rows = []
        for val, pg in persons.groupby(seg, sort=True):
            gg = g[g[seg] == val]
            contacts = int(pg.contacts.sum())
            rows.append({
                "segment": str(val), "n": int(len(pg)),
                "reach_pct": round(100 * pg.contacted.mean(), 1),
                "completed_per_100_contacts": round(100 * pg.done.sum() / contacts, 1) if contacts >= min_n else None,
                "gaps_closed_pct": round(100 * gg.closed.mean(), 1),
            })  # fmt: skip
        out[seg] = suppress_records(rows, min_n=min_n)
    return out
