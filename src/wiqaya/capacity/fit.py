"""Capacity fit with OR-Tools CP-SAT (PROMPT.md §6.4).

maximise  sum_i priority_i * P(attend | site) * week_factor  +  household same-week bonus
s.t.      each flag gets at most one (site, week); bucket capacity; slot-type match;
          travel-distance limit by phone type and housing; van only for adult slots near the stop.
Unassigned flags stay on the worklist ("waitlist") - the guardrail never drops a due gap.
"""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import time as dtime
from datetime import timedelta
from typing import Any

import pandas as pd
from ortools.sat.python import cp_model

from wiqaya.capacity.slots import Site, open_days, sites
from wiqaya.common import config as C
from wiqaya.common.geo import haversine_km


def max_km(p: Any) -> float:
    lim = C.cfg("simulation")["capacity_fit"]["max_km"]
    if p.housing_type == "labour_accommodation":
        return float(lim["labour_no_smartphone"] if p.phone_type != "smartphone" else lim["labour"])
    return float(lim["default"])


def candidates(flags: pd.DataFrame, people: pd.DataFrame, buckets: pd.DataFrame) -> pd.DataFrame:
    """Feasible (flag, site) pairs with distance."""
    cfg = C.cfg("simulation")["capacity_fit"]
    S = sites()
    ppl = people.set_index("id")
    clinic_sites = [s for s in S.values() if s.kind == "clinic"]
    van_sites = [s for s in S.values() if s.kind == "van"]
    rows = []
    for f in flags.itertuples(index=False):
        p = ppl.loc[f.person_id]
        dists = sorted((haversine_km(p.lat, p.lon, s.lat, s.lon), s.id) for s in clinic_sites)
        limit = max_km(p)
        chosen = [(d, sid) for d, sid in dists[: cfg["candidate_sites"]] if d <= limit]
        if not chosen:  # always keep the nearest clinic so nobody is unreachable by construction
            chosen = dists[:1]
        if f.slot_type == "adult" and p.housing_type == "labour_accommodation":
            for v in van_sites:
                d = haversine_km(p.lat, p.lon, v.lat, v.lon)
                if v.district_id == p.district_id and d <= 5:
                    chosen.append((d, v.id))
        for d, sid in chosen:
            rows.append({"flag_id": f.flag_id, "person_id": f.person_id, "site_id": sid, "distance_km": round(d, 2),
                         "is_van": S[sid].kind == "van"})  # fmt: skip
    return pd.DataFrame(rows)


def components(cand: pd.DataFrame) -> list[set[str]]:
    """Groups of sites connected through shared candidate flags (union-find); each is solved independently."""
    parent: dict[str, str] = {}

    def find(a: str) -> str:
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for _, g in cand.groupby("flag_id"):
        sites_ = list(g.site_id)
        for s in sites_[1:]:
            ra, rb = find(sites_[0]), find(s)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
        find(sites_[0])
    groups: dict[str, set[str]] = defaultdict(set)
    for s in parent:
        groups[find(s)].add(s)
    return [groups[k] for k in sorted(groups)]


def _solve_component(flags: pd.DataFrame, cand: pd.DataFrame, buckets: pd.DataFrame, p_attend: pd.Series,
                     seed: int, time_budget: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:  # fmt: skip
    """Stage 1 (CP-SAT): choose a site per flag against 12-week site capacity per slot type."""
    cfg = C.cfg("simulation")["capacity_fit"]
    model = cp_model.CpModel()
    fl = flags.set_index("flag_id")
    site_cap = buckets.groupby(["site_id", "slot_type"]).capacity.sum().to_dict()
    x: dict[tuple[str, str], cp_model.IntVar] = {}
    obj: list[Any] = []
    by_site: dict[tuple[str, str], list[Any]] = defaultdict(list)
    by_flag: dict[str, list[Any]] = defaultdict(list)
    for r in cand.itertuples(index=False):
        f = fl.loc[r.flag_id]
        if site_cap.get((r.site_id, f.slot_type), 0) <= 0:
            continue
        pa = float(p_attend.get((r.flag_id, r.site_id), 0.5))
        var = model.new_bool_var(f"x_{r.flag_id}_{r.site_id}")
        x[(r.flag_id, r.site_id)] = var
        obj.append(int(1000 * f.priority * pa) * var)
        by_site[(r.site_id, f.slot_type)].append(var)
        by_flag[r.flag_id].append(var)
    for vs in by_flag.values():
        model.add_at_most_one(vs)
    for key, vs in by_site.items():
        model.add(sum(vs) <= site_cap[key])
    bonus = int(1000 * cfg["household_same_day_bonus"])
    n_house = 0
    sites_by_flag: dict[str, set[str]] = defaultdict(set)
    for fid, s in x:
        sites_by_flag[fid].add(s)
    for hid, g in flags.groupby("household_id", sort=True):
        ids = [i for i in g.flag_id if i in sites_by_flag]
        if len(ids) < 2:
            continue
        for s in sorted(set.intersection(*[sites_by_flag[i] for i in ids])):
            y = model.new_bool_var(f"h_{hid}_{s}")
            for i in ids:
                model.add(y <= x[(i, s)])
            obj.append(bonus * len(ids) * y)
            n_house += 1
    model.maximize(sum(obj))
    solver = cp_model.CpSolver()
    # Deterministic: single worker, fixed seed, deterministic time budget.
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = seed
    solver.parameters.max_deterministic_time = time_budget
    status = solver.solve(model)
    ok = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    chosen = {f: s for (f, s), v in x.items() if ok and solver.value(v)}
    if not ok:
        chosen = {r["flag_id"]: r["site_id"] for r in greedy(flags, cand, buckets, p_attend)}
    return sequence_weeks(chosen, flags, buckets), {
        "status": solver.status_name(status),
        "variables": len(x),
        "household_vars": n_house,
        "objective": solver.objective_value if ok else None,
        "best_bound": solver.best_objective_bound,
    }


def sequence_weeks(chosen: dict[str, str], flags: pd.DataFrame, buckets: pd.DataFrame) -> list[dict[str, Any]]:
    """Stage 2: within each site, fill weeks in order of time sensitivity then priority; households together."""
    fl = flags.set_index("flag_id")
    cap = {(r.site_id, r.week, r.slot_type): int(r.capacity) for r in buckets.itertuples(index=False)}
    weeks = sorted({w for (_, w, _) in cap})
    rows: list[dict[str, Any]] = []
    by_site: dict[str, list[str]] = defaultdict(list)
    for f, s in chosen.items():
        by_site[s].append(f)
    for s in sorted(by_site):
        ids = by_site[s]
        # Household key: members inherit the most urgent member's key so they are placed together.
        hh_key: dict[str, tuple[float, float]] = {}
        for f in ids:
            k = (float(fl.at[f, "rank"]), -float(fl.at[f, "time_sensitivity"]))  # rank already blends urgency
            h = fl.at[f, "household_id"]
            hh_key[h] = min(hh_key.get(h, k), k)
        order = sorted(
            ids, key=lambda f: (hh_key[fl.at[f, "household_id"]], fl.at[f, "household_id"], fl.at[f, "rank"])
        )
        for f in order:
            st = fl.at[f, "slot_type"]
            for w in weeks:
                if cap.get((s, w, st), 0) > 0:
                    cap[(s, w, st)] -= 1
                    rows.append({"flag_id": f, "site_id": s, "week": w})
                    break
    return rows


def solve(flags: pd.DataFrame, cand: pd.DataFrame, buckets: pd.DataFrame, p_attend: pd.Series,
          seed: int) -> tuple[pd.DataFrame, dict[str, Any]]:  # fmt: skip
    """Solve each connected group of sites as its own CP-SAT model (laptop-sized, deterministic)."""
    cfg = C.cfg("simulation")["capacity_fit"]
    t_start = time.perf_counter()
    rows: list[dict[str, Any]] = []
    comps = []
    total_vars = 0
    for i, sites_ in enumerate(components(cand)):
        c = cand[cand.site_id.isin(sites_)]
        fids = set(c.flag_id)
        f = flags[flags.flag_id.isin(fids)]
        b = buckets[buckets.site_id.isin(sites_)]
        r, st = _solve_component(f, c, b, p_attend, seed + i, float(cfg["time_limit_seconds"]))
        rows += r
        total_vars += st["variables"]
        comps.append({"sites": len(sites_), "flags": len(fids), **st})
    statuses = {c["status"] for c in comps}
    return pd.DataFrame(rows), {
        "method": "CP-SAT site choice per component + deterministic week sequencing",
        "status": "OPTIMAL" if statuses == {"OPTIMAL"} else "/".join(sorted(statuses)),
        "components": len(comps),
        "variables": total_vars,
        "optimal_components": sum(c["status"] == "OPTIMAL" for c in comps),
        "largest_component_flags": max((c["flags"] for c in comps), default=0),
        "seconds": round(time.perf_counter() - t_start, 1),
        "detail": comps,
    }


def greedy(flags: pd.DataFrame, cand: pd.DataFrame, buckets: pd.DataFrame,
           p_attend: pd.Series | None = None) -> list[dict[str, Any]]:  # fmt: skip
    """Rank order; best expected-attendance site; earliest week with room; household members follow."""
    cap = {(r.site_id, r.week, r.slot_type): int(r.capacity) for r in buckets.itertuples(index=False)}
    weeks = sorted({w for (_, w, _) in cap})
    pa = p_attend if p_attend is not None else pd.Series(dtype=float)
    sites_by_flag: dict[str, list[str]] = {}
    for fid, g in cand.groupby("flag_id"):
        sites_by_flag[fid] = sorted(g.site_id, key=lambda s, _f=fid: -float(pa.get((_f, s), 0.5)))  # type: ignore[misc]
    fl = flags.set_index("flag_id")
    placed: dict[str, tuple[str, int]] = {}
    hh_slot: dict[str, tuple[str, int]] = {}
    for f in flags.sort_values("rank").itertuples(index=False):
        st = f.slot_type
        options = sites_by_flag.get(f.flag_id, [])
        pref = hh_slot.get(f.household_id)
        tries: list[tuple[str, int]] = []
        if pref and pref[0] in options:
            tries.append(pref)
        tries += [(s, w) for s in options for w in weeks]
        for s, w in tries:
            if cap.get((s, w, st), 0) > 0:
                cap[(s, w, st)] -= 1
                placed[f.flag_id] = (s, w)
                hh_slot.setdefault(fl.loc[f.flag_id, "household_id"], (s, w))
                break
    return [{"flag_id": k, "site_id": s, "week": w} for k, (s, w) in placed.items()]


def bundle_households(assign: pd.DataFrame, flags: pd.DataFrame, buckets: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Post-pass: move household members at the same site into the household's earliest week.

    A move uses spare capacity or swaps weeks with a lower-priority, non-bundled flag of the same slot type,
    so bucket capacity is never exceeded.
    """
    if assign.empty:
        return assign, 0
    fl = flags.set_index("flag_id")
    a = assign.copy()
    a["household_id"] = a.flag_id.map(fl.household_id)
    a["slot_type"] = a.flag_id.map(fl.slot_type)
    a["priority"] = a.flag_id.map(fl.priority)
    cap = {(r.site_id, r.week, r.slot_type): int(r.capacity) for r in buckets.itertuples(index=False)}
    used = a.groupby(["site_id", "week", "slot_type"]).size().to_dict()
    hh_size = a.groupby("household_id").size()
    multi = a.groupby(["household_id", "site_id"]).filter(lambda g: g.week.nunique() > 1)
    moves = 0
    for (hid, sid), g in multi.groupby(["household_id", "site_id"], sort=True):
        counts = g.week.value_counts()
        target = int(min(counts[counts == counts.max()].index))  # week holding most members, earliest on ties
        for idx in g[g.week != target].index:
            st = a.at[idx, "slot_type"]
            src = (sid, int(a.at[idx, "week"]), st)
            dst = (sid, target, st)
            if used.get(dst, 0) < cap.get(dst, 0):
                used[dst] = used.get(dst, 0) + 1
                used[src] -= 1
                a.at[idx, "week"] = target
                moves += 1
                continue
            # Swap weeks with the lowest-priority single-person flag in the target bucket (same slot type).
            pool = a[(a.site_id == sid) & (a.week == target) & (a.slot_type == st)
                     & (a.household_id.map(hh_size) == 1)]  # fmt: skip
            if len(pool):
                swap = pool.priority.idxmin()
                a.at[swap, "week"], a.at[idx, "week"] = a.at[idx, "week"], target
                moves += 1
    return a[["flag_id", "site_id", "week"]], moves


def schedule_days(assign: pd.DataFrame, flags: pd.DataFrame, people: pd.DataFrame, start: Any) -> pd.DataFrame:
    """Turn (site, week) into a dated, timed slot. Household members at the same site/week share a day."""
    S: dict[str, Site] = sites()
    fl = flags.set_index("flag_id")
    ppl = people.set_index("id")
    out = []
    used: dict[tuple[str, Any], int] = defaultdict(int)
    for (sid, w), g in assign.groupby(["site_id", "week"], sort=True):
        site = S[sid]
        days = open_days(site, start + timedelta(days=7 * int(w)))
        if not days:
            continue
        g = g.assign(household_id=g.flag_id.map(fl.household_id), rank=g.flag_id.map(fl["rank"]))
        groups = sorted(g.groupby("household_id"), key=lambda kv: kv[1]["rank"].min())
        for i, (hid, hg) in enumerate(groups):
            day = min(days, key=lambda d: (used[(sid, d)], (d - days[0]).days))
            for f in hg.sort_values("rank").itertuples(index=False):
                p = ppl.loc[fl.loc[f.flag_id, "person_id"]]
                n = used[(sid, day)]
                if site.kind == "van" or p.housing_type == "labour_accommodation":
                    oh, om = (int(v) for v in site.open_time.split(":"))
                    base = dtime(17, 0) if site.kind != "van" else dtime(oh, om)
                else:
                    base = dtime(8, 30)
                minutes = base.hour * 60 + base.minute + 20 * (n % 30)
                out.append({"flag_id": f.flag_id, "person_id": fl.loc[f.flag_id, "person_id"], "site_id": sid,
                            "site_kind": site.kind, "week": int(w), "date": day,
                            "time": f"{minutes // 60:02d}:{minutes % 60:02d}",
                            "household_bundled": len(hg) > 1})  # fmt: skip
                used[(sid, day)] += 1
    return pd.DataFrame(out)
