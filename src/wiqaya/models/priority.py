"""Priority score (PROMPT.md §6.3). It changes ORDER and outreach intensity only; every due gap stays listed.

priority = w_r * risk + w_t * time_sensitivity + w_n * no_show_risk + w_h * household_bundle_bonus
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from wiqaya.common import config as C
from wiqaya.rules.schema import load_rules


def gap_time_sensitivity(gaps: pd.DataFrame, people: pd.DataFrame, as_of: date) -> pd.Series:
    pr = C.cfg("simulation")["priority"]
    ts_map = pr["time_sensitivity"]
    birth = people.set_index("id")["birth_date"]
    base = gaps.pathway.map(ts_map).fillna(0.4)
    boost = np.where(gaps.days_overdue > pr["overdue_boost_days"], pr["overdue_boost"], 0.0)
    age = gaps.person_id.map(lambda pid: (as_of - birth[pid]).days / 365.25)
    infant = np.where(age < 2, pr["infant_boost"], 0.0)
    return pd.Series(np.clip(base + boost + infant, 0, 1), index=gaps.index)


def build_flags(gaps: pd.DataFrame, people: pd.DataFrame, risk: pd.Series, noshow: pd.Series,
                shap_top3: dict[str, list[dict[str, Any]]], as_of: date) -> pd.DataFrame:  # fmt: skip
    """One flag per person with open gaps, ranked by priority."""
    pr = C.cfg("simulation")["priority"]
    w = pr["weights"]
    rules = {r.id: r for r in load_rules()}
    g = gaps.copy()
    g["ts"] = gap_time_sensitivity(g, people, as_of)
    hh = people.set_index("id")["household_id"]
    g["household_id"] = g.person_id.map(hh)
    hh_people_with_gaps = g.groupby("household_id")["person_id"].nunique()
    # Risk: percentile rank of calibrated risk among scored adults; people without a score get the median.
    risk_pct = risk.rank(pct=True)
    rows = []
    for pid, pg in g.groupby("person_id", sort=True):
        top = pg.sort_values(["ts", "days_overdue"], ascending=False).iloc[0]
        r_cal = float(risk.get(pid, np.nan))
        r_pct = float(risk_pct.get(pid, 0.5)) if not np.isnan(r_cal) else 0.5
        risk_note = "model" if not np.isnan(r_cal) else "no model score (children): neutral 0.5"
        if (pg.pathway == "cascade").any():
            # Guideline prior: a first-degree relative of a confirmed FH/BRCA index has ~50% carrier probability,
            # far above any population model estimate. The rule, not the model, sets this component.
            r_pct = max(r_pct, pr["cascade_risk_percentile"])
            risk_note = "guideline prior: first-degree relative of an index case (cascade rule)"
        ts = float(pg.ts.max())
        ns = float(noshow.get(pid, noshow.median() if len(noshow) else 0.5))
        bundle = float(hh_people_with_gaps.get(top.household_id, 1) >= 2)
        priority = w["risk"] * r_pct + w["time_sensitivity"] * ts + w["no_show"] * ns + w["household_bundle"] * bundle
        rule = rules[top.rule_id]
        rows.append({
            "flag_id": f"flag-{pid}", "person_id": pid, "household_id": top.household_id,
            "gap_ids": json.dumps(sorted(pg.id)), "rules": json.dumps(sorted(pg.rule_ref)),
            "n_gaps": len(pg), "top_rule_id": top.rule_id, "top_pathway": top.pathway, "top_status": top.status,
            "max_days_overdue": int(pg.days_overdue.max()), "requires_clinician": bool(pg.requires_clinician.any()),
            "slot_type": rule.slot_type, "message_pathway": rule.message_pathway,
            "risk_calibrated": None if np.isnan(r_cal) else round(r_cal, 4), "risk_percentile": round(r_pct, 4),
            "risk_note": risk_note,
            "time_sensitivity": round(ts, 3), "no_show_risk": round(ns, 4), "household_bundle_bonus": bundle,
            "priority": round(float(priority), 5),
            "shap_top3": json.dumps(shap_top3.get(pid, [])),
            "reviewer_decision": "pending", "reviewer_note": "",
        })  # fmt: skip
    flags = pd.DataFrame(rows)
    flags = flags.sort_values(["priority", "person_id"], ascending=[False, True], kind="mergesort").reset_index(
        drop=True
    )
    flags["rank"] = np.arange(1, len(flags) + 1)
    q = flags.priority.rank(pct=True)
    flags["band"] = np.where(q >= pr["bands"]["high"], "high", np.where(q >= pr["bands"]["medium"], "medium", "low"))
    return flags
