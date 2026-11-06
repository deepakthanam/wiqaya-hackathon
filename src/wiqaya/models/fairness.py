"""Fairness floor (PROMPT.md §6.3).

After ranking, each monitoring segment's share of the K slot-eligible flags must be at least
floor_ratio x its need-adjusted share (its share of people with open high-time-sensitivity gaps).
Below the floor, the segment's next-highest-priority flags are promoted, displacing the lowest-ranked
flags of segments that stay above their floor. Every adjustment is logged.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from wiqaya.common import config as C

SEGMENT_COLUMNS = {"nationality_group": "nationality_group", "language": "preferred_language",
                   "district": "district_id", "housing_type": "housing_type", "insurance_tier": "insurance_tier"}  # fmt: skip
HIGH_TS = 0.7


def apply_floor(flags: pd.DataFrame, people: pd.DataFrame, k: int,
                floor_ratio: float | None = None) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:  # fmt: skip
    cfg = C.cfg("segments")["fairness"]
    floor_ratio = cfg["floor_ratio"] if floor_ratio is None else floor_ratio
    seg = people.set_index("id")
    f = flags.copy().sort_values("rank").reset_index(drop=True)
    for name in cfg["segments"]:
        f[name] = f.person_id.map(seg[SEGMENT_COLUMNS[name]])
    k = min(k, len(f))
    order = list(f.index)  # current ranking (positions)
    log: list[dict[str, Any]] = []
    need_pool = f[f.time_sensitivity >= HIGH_TS]
    report: dict[str, Any] = {}
    for name in cfg["segments"]:
        need = need_pool[name].value_counts(normalize=True)
        for _ in range(len(need) * 3):  # bounded passes
            top = f.loc[order[:k], name].value_counts()
            targets = {v: math.ceil(floor_ratio * need[v] * k) for v in need.index}
            deficits = {v: targets[v] - int(top.get(v, 0)) for v in need.index if int(top.get(v, 0)) < targets[v]}
            if not deficits:
                break
            changed = False
            for v, d in sorted(deficits.items(), key=lambda kv: -kv[1]):
                candidates = [i for i in order[k:] if f.at[i, name] == v][:d]
                for cand in candidates:
                    # Lowest-ranked top-K flag whose segment stays at/above its own target after removal.
                    counts = f.loc[order[:k], name].value_counts()
                    victim = next((i for i in reversed(order[:k])
                                   if f.at[i, name] != v and counts.get(f.at[i, name], 0) - 1 >= targets.get(f.at[i, name], 0)),
                                  None)  # fmt: skip
                    if victim is None:
                        break
                    pi, pv = order.index(cand), order.index(victim)
                    order[pi], order[pv] = order[pv], order[pi]
                    log.append({"dimension": name, "segment": str(v), "promoted": f.at[cand, "flag_id"],
                                "promoted_from_rank": int(f.at[cand, "rank"]), "demoted": f.at[victim, "flag_id"],
                                "demoted_from_rank": int(f.at[victim, "rank"]),
                                "reason": f"slot share below {floor_ratio} x need share"})  # fmt: skip
                    changed = True
            if not changed:
                break
        top = f.loc[order[:k], name].value_counts()
        report[name] = {str(v): {"need_share": round(float(need[v]), 4),
                                 "slot_share": round(float(top.get(v, 0)) / k, 4),
                                 "ratio": round((float(top.get(v, 0)) / k) / float(need[v]), 3) if need[v] else None,
                                 "meets_floor": float(top.get(v, 0)) / k >= floor_ratio * float(need[v]) - 1 / k}
                        for v in need.index}  # fmt: skip
    out = f.loc[order].reset_index(drop=True)
    out["rank_before_fairness"] = out["rank"]
    out["rank"] = range(1, len(out) + 1)
    out["fairness_adjusted"] = out.flag_id.isin({e["promoted"] for e in log} | {e["demoted"] for e in log})
    return out.drop(columns=list(cfg["segments"])), log, report
