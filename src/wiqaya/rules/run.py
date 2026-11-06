"""`run_gaps(as_of)`: evaluate every rule for every consented person (PROMPT.md §6.1)."""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import date, timedelta
from typing import Any

import pandas as pd

from wiqaya.common import config as C
from wiqaya.graph.family import build_graph, cascade_links, index_people
from wiqaya.rules.engine import CareGap, EngineContext, evaluate
from wiqaya.rules.schema import Rule, load_rules
from wiqaya.rules.snapshot import PersonSnapshot, SnapshotView
from wiqaya.store import repo


def build_snapshots(t: dict[str, pd.DataFrame], as_of: date, links: dict[str, list[Any]],
                    cmap: dict[tuple[str, str], str]) -> dict[str, PersonSnapshot]:  # fmt: skip
    snaps: dict[str, PersonSnapshot] = {}
    for p in t["people"].itertuples(index=False):
        snaps[p.id] = PersonSnapshot(person_id=p.id, birth_date=p.birth_date, sex=p.sex)
    for r in t["conditions"].itertuples(index=False):
        s = snaps.get(r.person_id)
        if s is not None and r.verification == "confirmed" and r.onset_date <= as_of:
            prev = s.conditions.get(r.key)
            if prev is None or r.onset_date < prev:
                s.conditions[r.key] = r.onset_date
    obs = t["observations"].sort_values(["person_id", "key", "date"], kind="mergesort")
    for r in obs.itertuples(index=False):
        s = snaps.get(r.person_id)
        if s is not None and r.date <= as_of:
            s.observations.setdefault(r.key, []).append((r.date, float(r.value)))
    enc = t["encounters"].sort_values(["person_id", "date"], kind="mergesort")
    for r in enc.itertuples(index=False):
        s = snaps.get(r.person_id)
        if s is not None and r.attended and r.date <= as_of:
            s.encounters.setdefault(r.type, []).append(r.date)
    for r in t["immunizations"].itertuples(index=False):
        s = snaps.get(r.person_id)
        if s is not None and r.date <= as_of:
            s.immunizations.setdefault(r.vaccine, []).append(r.date)
    fh: dict[str, set[str]] = {}
    for r in t["family_history"].itertuples(index=False):
        fh.setdefault(r.person_id, set()).add(r.condition_key)
    gen: dict[str, list[tuple[str, str, date]]] = {}
    for r in t["genomic"].itertuples(index=False):
        if cmap.get((r.person_id, "genomic")) == "granted":  # privacy: genomic only with consent
            gen.setdefault(r.person_id, []).append((r.gene, r.classification, r.date))
    for pid, s in snaps.items():
        s.family_history = frozenset(fh.get(pid, set()))
        s.genomic = tuple(sorted(gen.get(pid, [])))
        s.cascade_links = tuple(links.get(pid, []))
        for v in s.immunizations.values():
            v.sort()
    return snaps


def engine_context(as_of: date) -> EngineContext:
    sim = C.cfg("simulation")
    months = C.cfg("population")["history_months"]
    return EngineContext(
        lookahead_days=int(sim["evaluation"]["lookahead_days"]),
        record_start=as_of - timedelta(days=int(months * 30.4375)),
        schedules=C.cfg("schedules"),
    )


def run_gaps(as_of: date | None = None, tables: dict[str, pd.DataFrame] | None = None,
             rules: tuple[Rule, ...] | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:  # fmt: skip
    t_start = time.perf_counter()
    as_of = as_of or C.t0()
    t = tables or repo.load()
    rules = rules or load_rules()
    cmap = repo.consent_map(t["consents"])
    graph, gstats = build_graph(t["relationships"], cmap)
    idx = index_people(rules, t["genomic"], t["conditions"], cmap, as_of)
    links = cascade_links(graph, idx)
    snaps = build_snapshots(t, as_of, links, cmap)
    ctx = engine_context(as_of)
    gaps: list[CareGap] = []
    excluded = {"denied": 0, "not_asked": 0}
    for pid, snap in snaps.items():
        status = cmap.get((pid, "clinical_data"), "not_asked")
        if status != "granted":
            excluded["denied" if status == "denied" else "not_asked"] += 1
            continue
        for rule in rules:
            g = evaluate(rule, SnapshotView(snap, rule.data_required), as_of, ctx)
            if g is not None:
                gaps.append(g)
    rows = []
    for g in gaps:
        d = asdict(g)
        d["rule_ref"] = g.rule_ref
        d["evidence"] = json.dumps(d["evidence"], sort_keys=True, default=str)
        d["fields_read"] = json.dumps(d["fields_read"])
        rows.append(d)
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["person_id", "rule_id"], kind="mergesort").reset_index(drop=True)
    stats = {
        "as_of": as_of.isoformat(),
        "people": len(snaps),
        "people_evaluated": len(snaps) - sum(excluded.values()),
        "excluded_by_consent": excluded,
        "gaps": len(df),
        "people_with_gap": int(df["person_id"].nunique()) if len(df) else 0,
        "by_rule": df.groupby("rule_id").size().to_dict() if len(df) else {},
        "by_status": df.groupby("status").size().to_dict() if len(df) else {},
        "index_people": len(idx),
        "graph": gstats,
        "seconds": round(time.perf_counter() - t_start, 2),
    }
    return df, stats


def persist_gaps(df: pd.DataFrame, stats: dict[str, Any]) -> None:
    """Write care_gaps to DuckDB + Parquet and DetectedIssue NDJSON (for HAPI)."""
    from wiqaya.common.paths import NDJSON_DIR, PARQUET_DIR, RUNS_DIR
    from wiqaya.fhir.ndjson import dumps
    from wiqaya.fhir.resources import detected_issue

    repo.write_table("care_gaps", df)
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PARQUET_DIR / "care_gaps.parquet", index=False)
    rules = {r.id: r for r in load_rules()}
    with (NDJSON_DIR / "DetectedIssue.ndjson").open("w", encoding="utf-8", newline="\n") as fh:
        for row in df.to_dict("records"):
            r = rules[row["rule_id"]]
            fh.write(dumps(detected_issue(row, r.source.url, r.output_codes["gap_code"], r.title)) + "\n")
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    (RUNS_DIR / "gaps_stats.json").write_text(json.dumps(stats, indent=1, default=str), encoding="utf-8")
