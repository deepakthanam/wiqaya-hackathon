"""Pure care-gap evaluator.

`evaluate(rule, view, as_of, ctx)` -> `CareGap | None`. No I/O, no randomness, no clock:
the same inputs always give the same output. Each gap is version-pinned (`rule_id@version`)
and traced (`evidence`, `fields_read`).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from wiqaya.rules.schema import Criterion, Rule
from wiqaya.rules.snapshot import SnapshotView

DAYS_PER_MONTH = 30.4375
OVERDUE_GRACE_DAYS = 30


@dataclass(frozen=True)
class EngineContext:
    lookahead_days: int = 90
    record_start: date | None = None  # start of available history (for evidence text)
    schedules: dict[str, Any] = field(default_factory=dict)


@dataclass
class CareGap:
    id: str
    person_id: str
    rule_id: str
    rule_version: str
    pathway: str
    status: str  # due | overdue | missed | eligible_early | followup_overdue
    due_date: date
    days_overdue: int
    evidence: dict[str, Any]
    fields_read: list[str]
    requires_clinician: bool
    created_at: date

    @property
    def rule_ref(self) -> str:
        return f"{self.rule_id}@{self.rule_version}"


def _age_years(birth: date, on: date) -> float:
    return (on - birth).days / 365.25


def _add_months(d: date, months: float) -> date:
    return d + timedelta(days=round(months * DAYS_PER_MONTH))


def _add_years(d: date, years: float) -> date:
    return d + timedelta(days=round(years * 365.25))


def gap_id(person_id: str, rule_id: str, as_of: date) -> str:
    h = hashlib.sha1(f"{person_id}|{rule_id}|{as_of.isoformat()}".encode()).hexdigest()[:12]
    return f"gap-{h}"


def _criterion_holds(c: Criterion, v: SnapshotView, ev: dict[str, Any]) -> bool:
    ok = True
    if c.bmi_min is not None:
        bmi = v.get("bmi_latest")
        ev["bmi_latest"] = bmi
        ok = ok and bmi is not None and bmi >= c.bmi_min
    if c.conditions_any:
        conds = v.get("conditions")
        hit = [x for x in c.conditions_any if x in conds]
        ok = ok and bool(hit)
        if hit:
            ev["conditions"] = hit
    if c.family_history_any:
        fh = v.get("family_history")
        hit = [x for x in c.family_history_any if x in fh]
        ok = ok and bool(hit)
        if hit:
            ev["family_history"] = hit
    return ok


def _excluded(rule: Rule, v: SnapshotView) -> list[str]:
    if not rule.applies_to.exclude_conditions:
        return []
    conds = v.get("conditions")
    return [c for c in rule.applies_to.exclude_conditions if c in conds]


def _status_from_days(days: int, early: bool) -> str:
    if early:
        return "eligible_early"
    return "overdue" if days > OVERDUE_GRACE_DAYS else "due"


def _mk(
    rule: Rule,
    v: SnapshotView,
    as_of: date,
    status: str,
    due: date,
    ev: dict[str, Any],
) -> CareGap:
    return CareGap(
        id=gap_id(v.person_id, rule.id, as_of),
        person_id=v.person_id,
        rule_id=rule.id,
        rule_version=rule.version,
        pathway=rule.pathway,
        status=status,
        due_date=due,
        days_overdue=(as_of - due).days,
        evidence=ev,
        fields_read=list(v.fields_read),
        requires_clinician=rule.requires_clinician,
        created_at=as_of,
    )


# --------------------------------------------------------------------------------- periodic
def _periodic(rule: Rule, v: SnapshotView, as_of: date, ctx: EngineContext) -> CareGap | None:
    birth: date = v.get("birth_date")
    age = _age_years(birth, as_of)
    ev: dict[str, Any] = {"age_years": round(age, 1)}
    a = rule.applies_to
    if a.sex is not None:
        sex = v.get("sex")
        if sex != a.sex:
            return None
    excl = _excluded(rule, v)
    if excl:
        return None
    in_age = a.age_years is None or a.age_years.contains(age)
    criteria_ok = not a.any_of or any(_criterion_holds(c, v, ev) for c in a.any_of)
    early = False
    eligible_from = _add_years(birth, a.age_years.min) if a.age_years and a.age_years.min else birth
    if not (in_age and criteria_ok):
        for e in rule.eligible_early:
            if (
                e.age_years.contains(age)
                and _criterion_holds(e.when, v, ev)
                and (a.age_years is None or a.age_years.max is None or age <= a.age_years.max)
            ):
                early = True
                ev["eligible_early_reason"] = e.reason
                eligible_from = _add_years(birth, e.age_years.min or 0)
                break
        if not early:
            return None

    # Latest satisfying event across sources.
    last: tuple[date, str, float | None] | None = None
    for src in rule.satisfied_by:
        for d, val in v.events(src):
            if d <= as_of and (last is None or d > last[0]):
                last = (d, src, val)

    interval = rule.interval_months
    for iba in rule.interval_by_age:
        if iba.age_years.contains(age):
            interval = iba.interval_months
    if last and rule.interval_by_test:
        key = last[1].split(":", 1)[1]
        interval = rule.interval_by_test.get(key, interval)
    for ov in rule.interval_overrides:
        series = v.get(f"obs:{ov.obs}")
        if series and ov.range.contains(series[-1][1]) and interval is not None:
            if ov.interval_months < interval:
                interval = ov.interval_months
                ev["interval_reason"] = ov.reason
    assert interval is not None

    if last is None:
        due = eligible_from
        ev["last_done"] = None
        ev["note"] = "no record of this check in the available history"
    else:
        due = _add_months(last[0], interval)
        ev["last_done"] = last[0].isoformat()
        ev["last_source"] = last[1]
        if last[2] is not None:
            ev["last_value"] = last[2]
    ev["interval_months"] = interval
    days = (as_of - due).days
    if days < -ctx.lookahead_days:
        return None
    return _mk(rule, v, as_of, _status_from_days(days, early), due, ev)


# --------------------------------------------------------------------------------- schedule
def _milestones(rule: Rule, ctx: EngineContext) -> tuple[list[tuple[str, float]], int, int]:
    sch = ctx.schedules[rule.schedule_ref or ""]
    if "visits" in sch:
        ms = [(k, float(m)) for k, m in sch["visits"].items()]
        for y in range(int(sch["yearly_from_years"]), int(sch["yearly_to_years"]) + 1):
            ms.append((f"y{y}", y * 12.0))
    else:
        ms = [(f"m{m}", float(m)) for m in sch["ages_months"]]
    return sorted(ms, key=lambda x: x[1]), int(sch["window_before_days"]), int(sch["window_after_days"])


def _schedule(rule: Rule, v: SnapshotView, as_of: date, ctx: EngineContext) -> CareGap | None:
    birth: date = v.get("birth_date")
    age = _age_years(birth, as_of)
    if rule.applies_to.age_years and not rule.applies_to.age_years.contains(age):
        return None
    ms, before, after = _milestones(rule, ctx)
    horizon = as_of + timedelta(days=ctx.lookahead_days)
    current = [(k, m) for k, m in ms if _add_months(birth, m) - timedelta(days=before) <= horizon]
    if not current:
        return None
    events = sorted(d for src in rule.satisfied_by for d, _ in v.events(src) if d <= as_of)

    def done(m: float) -> bool:
        t = _add_months(birth, m)
        return any(t - timedelta(days=before) <= d <= t + timedelta(days=after) for d in events)

    key, m = current[-1]
    if done(m):
        return None
    target = _add_months(birth, m)
    record_start = ctx.record_start or date.min
    missed_before = [k for k, mm in current[:-1] if _add_months(birth, mm) >= record_start and not done(mm)]
    ev: dict[str, Any] = {
        "age_months": round(age * 12, 1),
        "milestone": key,
        "milestone_target": target.isoformat(),
        "earlier_missed_in_record": missed_before,
        "last_done": events[-1].isoformat() if events else None,
    }
    window_end = target + timedelta(days=after)
    if as_of <= window_end:
        status = "due"
    elif (as_of - window_end).days > 180:
        status = "missed"
    else:
        status = "overdue"
    return _mk(rule, v, as_of, status, target, ev)


# ----------------------------------------------------------------------------- immunisation
def _immunisation(rule: Rule, v: SnapshotView, as_of: date, ctx: EngineContext) -> CareGap | None:
    birth: date = v.get("birth_date")
    age = _age_years(birth, as_of)
    if rule.applies_to.age_years and not rule.applies_to.age_years.contains(age):
        return None
    sch = ctx.schedules[rule.schedule_ref or ""]
    grace = int(sch.get("grace_days", 30))
    received: dict[str, list[date]] = v.get("immunizations")
    horizon = as_of + timedelta(days=ctx.lookahead_days)
    need_count: dict[str, int] = {}
    missing: list[dict[str, Any]] = []
    for dose in sch["doses"]:
        vac = dose["vaccine"]
        need_count[vac] = need_count.get(vac, 0) + 1
        n_needed = need_count[vac]
        target = _add_months(birth, float(dose["age_months"]))
        if target > horizon:
            continue
        max_age = dose.get("max_age_months")
        if max_age is not None and age * 12 > float(max_age):
            continue
        if len([d for d in received.get(vac, []) if d <= as_of]) >= n_needed:
            continue
        missing.append({"vaccine": vac, "dose": dose["dose"], "target": target})
    if not missing:
        return None
    earliest = min(x["target"] for x in missing)
    days = (as_of - earliest).days
    status = "overdue" if days > grace else "due"
    ev = {
        "age_months": round(age * 12, 1),
        "missing_doses": [f"{x['vaccine']}#{x['dose']}" for x in missing],
        "schedule_status": sch.get("status", ""),
    }
    return _mk(rule, v, as_of, status, earliest, ev)


# --------------------------------------------------------------------------------- follow-up
def _followup(rule: Rule, v: SnapshotView, as_of: date, ctx: EngineContext) -> CareGap | None:
    assert rule.trigger is not None and rule.followup_window_months is not None
    birth: date = v.get("birth_date")
    age = _age_years(birth, as_of)
    if rule.applies_to.age_years and not rule.applies_to.age_years.contains(age):
        return None
    if _excluded(rule, v):
        return None
    lookback = _add_months(as_of, -rule.trigger.lookback_months)
    trigger_date: date | None = None
    trig_ev: dict[str, Any] = {}
    for cond in rule.trigger.any_of:
        key = str(cond["obs"])
        series = [(d, x) for d, x in v.get(f"obs:{key}") if lookback <= d <= as_of]
        if not series:
            continue
        d, x = series[-1]
        lo, hi = cond.get("min"), cond.get("max")
        if (lo is None or x >= float(lo)) and (hi is None or x <= float(hi)):
            if trigger_date is None or d > trigger_date:
                trigger_date = d
            trig_ev[key] = x
            trig_ev[f"{key}_date"] = d.isoformat()
    if trigger_date is None:
        return None
    for src in rule.satisfied_by:
        if any(trigger_date < d <= as_of for d, _ in v.events(src)):
            return None
    due = _add_months(trigger_date, rule.followup_window_months)
    days = (as_of - due).days
    if days < -ctx.lookahead_days:
        return None
    ev = {"trigger": trig_ev, "window_months": rule.followup_window_months}
    return _mk(rule, v, as_of, "followup_overdue" if days > 0 else "due", due, ev)


# ----------------------------------------------------------------------------------- cascade
def _cascade(rule: Rule, v: SnapshotView, as_of: date, ctx: EngineContext) -> CareGap | None:
    c = rule.cascade
    assert c is not None
    birth: date = v.get("birth_date")
    age = _age_years(birth, as_of)
    wanted = {f"gene:{g}" for g in c.index_genes} | {f"condition:{x}" for x in c.index_conditions}
    links = []
    for link in v.get("cascade_links"):
        if link.reason not in wanted or link.relationship not in c.relationships:
            continue
        min_age = c.child_min_age_years if link.relationship == "child" else c.relative_min_age_years
        if age < min_age:
            continue
        links.append(link)
    if not links:
        return None
    first = min(link.index_date for link in links)
    for src in rule.satisfied_by:
        if any(first < d <= as_of for d, _ in v.events(src)):
            return None
    ev = {
        "index_links": len(links),
        "relationships": sorted({link.relationship for link in links}),
        "index_person_ids": sorted({link.index_person_id for link in links}),  # clinician-only field
        "index_reasons": sorted({link.reason for link in links}),  # clinician-only field
        "outreach_allowed_after_approval": c.outreach_allowed_after_approval,
    }
    return _mk(rule, v, as_of, "due", first, ev)


_KINDS = {
    "periodic": _periodic,
    "schedule": _schedule,
    "immunisation": _immunisation,
    "followup": _followup,
    "cascade": _cascade,
}


def evaluate(rule: Rule, view: SnapshotView, as_of: date, ctx: EngineContext) -> CareGap | None:
    """Evaluate one rule for one person. Pure and deterministic."""
    return _KINDS[rule.kind](rule, view, as_of, ctx)
