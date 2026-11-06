"""`make train`: train + calibrate models, score at T0, rank, fairness floor, capacity fit."""

from __future__ import annotations

import json
import pickle
import time
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from wiqaya.capacity.fit import bundle_households, candidates, schedule_days, solve
from wiqaya.capacity.slots import build_capacity, sites
from wiqaya.common import config as C
from wiqaya.common.geo import haversine_km
from wiqaya.common.paths import DATA, RUNS_DIR
from wiqaya.models.explain import top3
from wiqaya.models.fairness import apply_floor
from wiqaya.models.features import FEATURES_R, noshow_scoring, noshow_training, risk_features
from wiqaya.models.priority import build_flags
from wiqaya.models.train import CalibratedModel, train_noshow, train_risk
from wiqaya.outreach.plan import Planner
from wiqaya.store import repo

MODELS_DIR = DATA / "models"


def plan_contacts(t: dict[str, pd.DataFrame], pids: list[str], as_of: date) -> dict[str, tuple[str, str]]:
    planner = Planner(t, as_of)
    out = {}
    for pid in pids:
        cp = planner.plan(pid)
        out[pid] = (cp.channels[0] if cp.channels else "chw_script", cp.language)
    return out


def score(t: dict[str, pd.DataFrame], gaps: pd.DataFrame, model_r: CalibratedModel, model_n: CalibratedModel,
          as_of: date) -> tuple[pd.Series, pd.Series, dict[str, Any], dict[str, tuple[str, str]]]:  # fmt: skip
    pids = sorted(gaps.person_id.unique())
    Xr = risk_features(t, as_of, t["people"][t["people"].id.isin(pids)])
    risk = pd.Series(model_r.predict(Xr), index=Xr.person_id.values) if len(Xr) else pd.Series(dtype=float)
    shap = dict(zip(Xr.person_id, top3(model_r, Xr), strict=True)) if len(Xr) else {}
    plan = plan_contacts(t, pids, as_of)
    Xn = noshow_scoring(t, plan)
    noshow = pd.Series(model_n.predict(Xn), index=Xn.person_id.values)
    return risk, noshow, shap, plan


def p_attend_by_site(t: dict[str, pd.DataFrame], cand: pd.DataFrame, plan: dict[str, tuple[str, str]],
                     model_n: CalibratedModel) -> pd.Series:  # fmt: skip
    base = noshow_scoring(t, {pid: plan[pid] for pid in cand.person_id.unique()}).set_index("person_id")
    X = base.loc[cand.person_id].reset_index()
    X["distance_km"] = cand.distance_km.to_numpy()
    p = 1 - model_n.predict(X)
    return pd.Series(p, index=pd.MultiIndex.from_arrays([cand.flag_id, cand.site_id]))


def run(seed: int | None = None) -> dict[str, Any]:
    t_start = time.perf_counter()
    sim = C.cfg("simulation")
    seed = seed if seed is not None else sim["seeds"]["models"]
    as_of = C.t0()
    t = repo.load()
    gaps = repo.read_table("care_gaps")
    model_r, _ = train_risk(t, seed)
    model_n = train_noshow(noshow_training(t), t, seed)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for m in (model_r, model_n):
        (MODELS_DIR / f"{m.name}.pkl").write_bytes(pickle.dumps(m))
    risk, noshow, shap, plan = score(t, gaps, model_r, model_n, as_of)
    flags = build_flags(gaps, t["people"], risk, noshow, shap, as_of)
    contact = Planner(t, as_of).as_records(list(flags.person_id))
    flags["recipient_id"] = flags.person_id.map(lambda p: contact[p]["recipient_id"])
    flags["audience"] = flags.person_id.map(lambda p: contact[p]["audience"])
    flags["channels"] = flags.person_id.map(lambda p: json.dumps(contact[p]["channels"]))
    flags["language_supported"] = flags.person_id.map(lambda p: contact[p]["language_supported"])
    flags["contact_reason"] = flags.person_id.map(lambda p: contact[p]["reason"])
    flags["channel_plan"] = flags.person_id.map(lambda p: plan[p][0])
    flags["language_plan"] = flags.person_id.map(lambda p: plan[p][1])
    start = date.fromisoformat(sim["evaluation"]["start"])
    n_weeks = int(sim["evaluation"]["weeks"])
    buckets = build_capacity(len(gaps), t["people"], start, n_weeks)
    k = int(buckets.capacity.sum())
    flags, fair_log, fair_report = apply_floor(flags, t["people"], k)
    # Only the top of the (fair) ranking can realistically get a slot; keep the problem laptop-sized.
    items = flags[flags["rank"] <= int(1.6 * k)].copy()
    cand = candidates(items, t["people"], buckets)
    pa = p_attend_by_site(t, cand, plan, model_n)
    assign, fit_stats = solve(items, cand, buckets, pa, seed)
    assign, fit_stats["household_moves"] = bundle_households(assign, items, buckets)
    sched = schedule_days(assign, items, t["people"], start)
    S = sites()
    ppl = t["people"].set_index("id")
    if len(sched):
        sched["distance_km"] = [round(haversine_km(ppl.loc[p, "lat"], ppl.loc[p, "lon"], S[s].lat, S[s].lon), 2)
                                for p, s in zip(sched.person_id, sched.site_id, strict=True)]  # fmt: skip
        sched["p_attend"] = [
            round(float(pa.get((f, s), np.nan)), 4) for f, s in zip(sched.flag_id, sched.site_id, strict=True)
        ]
    flags = flags.merge(sched[["flag_id", "site_id", "site_kind", "date", "time"]], on="flag_id", how="left")
    flags["slot_status"] = np.where(flags.site_id.notna(), "assigned", "waitlist")
    used = assign.merge(items[["flag_id", "slot_type"]], on="flag_id").groupby(["site_id", "week", "slot_type"]).size()
    over = [(k_, int(v), int(c)) for k_, v in used.items()
            for c in [buckets.set_index(["site_id", "week", "slot_type"]).capacity.get(k_, 0)] if v > c]  # fmt: skip
    repo.write_table("flags", flags)
    repo.write_table("assignments", sched)
    repo.write_table("capacity_buckets", buckets)
    repo.write_table("fairness_log", pd.DataFrame(fair_log) if fair_log else pd.DataFrame(
        columns=["dimension", "segment", "promoted", "promoted_from_rank", "demoted", "demoted_from_rank", "reason"]))  # fmt: skip
    metrics = {
        "seed": seed, "as_of": as_of.isoformat(), "model_r": model_r.metrics, "model_n": model_n.metrics,
        "features_r": FEATURES_R, "excluded_from_model_r": ["nationality_group", "preferred_language", "district_id",
                                                            "insurance_tier"],
        "flags": len(flags), "capacity_total": k, "flags_per_slot": round(len(flags) / k, 2),
        "assigned": int((flags.slot_status == "assigned").sum()), "van_assigned": int((sched.site_kind == "van").sum()),
        "household_bundled": int(sched.household_bundled.sum()) if len(sched) else 0,
        "capacity_violations": over, "fit": fit_stats, "fairness": {"adjustments": len(fair_log), "report": fair_report},
        "priority_weights": C.cfg("simulation")["priority"]["weights"],
        "seconds": round(time.perf_counter() - t_start, 1),
    }  # fmt: skip
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    (RUNS_DIR / "models.json").write_text(json.dumps(metrics, indent=1, default=str), encoding="utf-8")
    return metrics
