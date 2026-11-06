"""Calendar and cultural-timing rules (config/calendar.yaml, PROMPT.md §5.3)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import lru_cache
from typing import Any

from wiqaya.common import config as C

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _t(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


@lru_cache(maxsize=1)
def _cal() -> dict[str, Any]:
    cal = C.cfg("calendar")
    closed: dict[date, str] = {}
    for h in cal.get("public_holidays", []):
        closed[date.fromisoformat(h["date"])] = h["name"]
    no_send: dict[date, str] = dict(closed)
    for p in cal.get("no_send_periods", []):
        d, end = date.fromisoformat(p["start"]), date.fromisoformat(p["end"])
        while d <= end:
            no_send[d] = p["name"]
            if p.get("clinic_closed"):
                closed[d] = p["name"]
            d += timedelta(days=1)
    ramadan = [(date.fromisoformat(r["start"]), date.fromisoformat(r["end"]), r) for r in cal.get("ramadan", [])]
    exams = [
        (date.fromisoformat(e["start"]), date.fromisoformat(e["end"]), e) for e in cal.get("school_exam_windows", [])
    ]
    return {"cal": cal, "closed": closed, "no_send": no_send, "ramadan": ramadan, "exams": exams}


def weekday(d: date) -> str:
    return WEEKDAYS[d.weekday()]


def clinic_open(d: date, open_weekdays: list[str] | None = None) -> bool:
    days = open_weekdays or C.cfg("capacity")["open_weekdays"]
    return weekday(d) in days and d not in _cal()["closed"]


def closure_reason(d: date) -> str | None:
    r = _cal()["closed"].get(d)
    return None if r is None else str(r)


def in_ramadan(d: date) -> bool:
    return any(a <= d <= b for a, b, _ in _cal()["ramadan"])


def in_exam_window(d: date) -> str | None:
    for a, b, e in _cal()["exams"]:
        if a <= d <= b:
            return str(e["label"])
    return None


def summer_heat(d: date) -> bool:
    return d.month in _cal()["cal"]["summer_heat"]["months"]


def can_send(ts: datetime) -> tuple[bool, str]:
    """Whether a message may be sent at local time `ts` (Asia/Dubai)."""
    c = _cal()
    d, t = ts.date(), ts.time()
    if d in c["no_send"]:
        return False, f"no sends: {c['no_send'][d]}"
    q = c["cal"]["quiet_hours"]
    if t >= _t(q["start"]) or t < _t(q["end"]):
        return False, "quiet hours 21:00-08:00"
    fr = c["cal"]["friday_midday_no_send"]
    if d.weekday() == 4 and _t(fr["start"]) <= t < _t(fr["end"]):
        return False, "Friday midday prayers"
    if in_ramadan(d) and t < time(19, 30):
        return False, "Ramadan: send after iftar"
    return True, "ok"


def next_send_time(ts: datetime) -> tuple[datetime, list[str]]:
    """First allowed send time at or after `ts` (15-minute steps), with the reasons it was moved."""
    reasons: list[str] = []
    cur = ts
    for _ in range(24 * 4 * 14):
        ok, why = can_send(cur)
        if ok:
            return cur, reasons
        if why not in reasons:
            reasons.append(why)
        cur += timedelta(minutes=15)
    return cur, reasons
